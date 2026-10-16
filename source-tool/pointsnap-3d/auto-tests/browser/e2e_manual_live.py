"""Real CVAT 3D + unpacked MV3 extension. Creates and deletes ONLY its own temporary task.

Run with the project venv, after `python -m playwright install chromium`.
Uses an existing local project's PAT without printing it; no changes to that project.
"""
from __future__ import annotations

import argparse
import copy
import json
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

import numpy as np
import requests
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HERE/'tests'))
import fake_nuscenes
from pointsnap.adapters.cvat.client import CvatClient
from pointsnap.adapters.cvat.reader import load_job
from pointsnap.adapters.nuscenes import NuScenesReader
from pointsnap.core.serialize import save_cuboids, load_cuboids
from pointsnap.datasets.nuscenes.to_cvat import export_scene, upload_scene
from pointsnap.web.app import create_app


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',default='cvat-new',help='Existing local project used only to read URL/PAT')
    parser.add_argument('--out',default='out/manual-v2/live')
    parser.add_argument('--browser',choices=['chromium','msedge'],default='msedge')
    parser.add_argument('--software-rendering',action='store_true')
    args=parser.parse_args();out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    settings=Path.home()/'.pointsnap/projects'/args.project
    project=json.loads((settings/'project.json').read_text(encoding='utf-8'))
    token=json.loads((settings/'secret.json').read_text(encoding='utf-8'))['cvat_token']
    origin=project['cvat_url'].rstrip('/');client=CvatClient(origin,token)
    task_id=None;server=None;report={'checks':[],'errors':[]};context=None
    def check(label,value):
        if not value: raise AssertionError(label)
        report['checks'].append(label);print('PASS',label,flush=True)
    with tempfile.TemporaryDirectory(prefix='pointsnap-manual-') as temporary:
        temp=Path(temporary)
        try:
            data=fake_nuscenes.build(temp/'nuscenes')
            # Dense synthetic cloud, displayed by the real CVAT WebGL canvas.
            grid=np.array([(x,y,-2.,10.,0.) for x in np.linspace(-20,20,100) for y in np.linspace(-20,20,100)],dtype=np.float32)
            rng=np.random.default_rng(42)
            object_points=np.column_stack([rng.uniform(-1,1,500),rng.uniform(-12.25,-7.75,500),rng.uniform(-2,-.4,500),np.full(500,50),np.zeros(500)]).astype(np.float32)
            for f in (data/'samples/LIDAR_TOP').glob('*.bin'):np.concatenate([grid,object_points]).tofile(f)
            exported=export_scene(NuScenesReader(data),'scene-0001',temp/'export')
            boxes,meta=load_cuboids(exported.ground_truth)
            boxes=[b.replace(dims=(8,b.width,b.height),center=(b.center[0],b.center[1],b.center[2]+.3)) if b.label=='car' and b.frame==0 else b for b in boxes]
            save_cuboids(exported.ground_truth,boxes,meta)
            info=upload_scene(client,exported,'PointSnap v2 temporary browser test','pointsnap_error',timeout=120)
            task_id=info['task_id'];job_id=info['job_ids'][0]
            report['temporary_task_id']=task_id
            job=load_job(client,job_id);box=next(b for b in job.cuboids if b.label=='car' and b.frame==0)
            home=temp/'home';api=TestClient(create_app(home))
            r=api.post('/api/projects',json={'name':'Manual live','slug':'manual-live','cvat_url':origin,
                'export_dirs':[str(exported.directory)],'nuscenes_root':str(data)})
            check('isolated PointSnap project',r.status_code==201)
            api.put('/api/projects/manual-live/guideline',json={'config':{'size':{'manual_ranges':{'car':{'length':[3,5],'width':[1,3],'height':[1,3]}}}}})
            run=f'20261015-140000-job{job_id}';folder=home/'projects/manual-live/runs'/run;folder.mkdir(parents=True)
            findings=[]
            for rule,details in [('floating',{'ground_z':-2.,'distance':.3,'num_ground_points':100}),
                                 ('size.class_range',{}),('heading.flip',{'target_yaw_sensor':.3}),
                                 ('fit.outside',{'side':'đầu'})]:
                findings.append({'rule':rule,'error_type':'floating' if rule=='floating' else 'size' if rule.startswith('size') else 'heading' if rule.startswith('heading') else 'fit',
                    'frame':0,'track_id':box.track_id,'source_id':box.source_id,'label':box.label,'severity':'warning',
                    'message':'Dữ liệu lỗi kiểm thử · '+rule,'value':.3,'threshold':.1,'details':details})
            (folder/'findings.json').write_text(json.dumps(findings),encoding='utf-8')
            (folder/'summary.json').write_text(json.dumps({'job_id':job_id,'num_errors':0,'num_warnings':4,'num_boxes':len(job.cuboids),
                'cvat_url':origin,'timestamp':'2026-10-15T14:00:00+00:00','gate_verdict':'FAIL'}),encoding='utf-8')
            save_cuboids(folder/'snapshot.json',job.cuboids,{'task_id':task_id,'url':origin})
            port=8766
            log=(out/'backend.log').open('w',encoding='utf-8')
            server=subprocess.Popen([sys.executable,'-c',
                'import sys,uvicorn;from pointsnap.web.app import create_app;uvicorn.run(create_app(sys.argv[1]),host="127.0.0.1",port=8766,log_level="warning")',str(home)],
                cwd=HERE,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            for _ in range(100):
                try:
                    if requests.get(f'http://127.0.0.1:{port}/api/projects',timeout=.5).ok:break
                except requests.RequestException:pass
                time.sleep(.1)
            ext=temp/'extension';shutil.copytree(HERE/'extension',ext,ignore=shutil.ignore_patterns('tests'))
            manifest=json.loads((ext/'manifest.json').read_text(encoding='utf-8'))
            # Only the test backend's alternate port is added; all extension code is unchanged.
            manifest['host_permissions'].append(f'http://127.0.0.1:{port}/*')
            (ext/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
            before=client.get_job_annotations(job_id)
            writes=[];errors=[]
            with sync_playwright() as p:
                context=p.chromium.launch_persistent_context(str(temp/'profile'),channel=args.browser,headless=True,
                    ignore_default_args=['--disable-extensions'],
                    viewport={'width':1600,'height':1100},args=[f'--disable-extensions-except={ext}',f'--load-extension={ext}',
                    '--enable-unsafe-swiftshader']+(['--use-angle=swiftshader'] if args.software_rendering else []))
                worker=context.service_workers[0] if context.service_workers else context.wait_for_event('serviceworker')
                worker.evaluate("url=>chrome.storage.sync.set({pointsnapUrl:url,autoFilter:false,autoHighlight:false})",f'http://127.0.0.1:{port}')
                def route_api(route):
                    headers={**route.request.headers,'Authorization':'Bearer '+token}
                    route.continue_(headers=headers)
                context.route(origin+'/api/**',route_api)
                page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
                page.on('request',lambda r:writes.append(r.url) if '/annotations' in r.url and r.method in ('PUT','PATCH','POST') else None)
                page.goto(f'{origin}/tasks/{task_id}/jobs/{job_id}',timeout=60000)
                page.wait_for_function('!!window.cvatUI?.registerComponent',timeout=45000)
                page.evaluate("""() => window.cvatUI.registerComponent(({store})=>{window.__manualTestStore=store;return {name:'Manual test observer',destructor(){}};})""")
                page.wait_for_function("window.__manualTestStore.getState().annotation.canvas.ready",timeout=45000)
                check('real CVAT 3D loaded',page.locator('.cvat-canvas3d-topview canvas').count()==1)
                report['renderer']=page.evaluate("""() => { const gl=window.__manualTestStore.getState().annotation.canvas.instance.view.views.perspective.renderer.getContext();
                    const ext=gl.getExtension('WEBGL_debug_renderer_info');return ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER); }""")
                try:
                    page.wait_for_function("document.querySelector('#pointsnap-cvat-panel')?.shadowRoot.querySelector('[data-action=manual-rule]')",timeout=15000)
                except Exception:
                    debug=page.evaluate("""() => ({panel:document.querySelector('#pointsnap-cvat-panel')?.shadowRoot?.innerHTML,
                        bridge:!!window.PointSnapManualBridge,plugins:!!window.cvatUI,
                        compatible:window.PointSnapCvatCompat?.inspect(window.__manualTestStore)!=null})""")
                    debug['errors']=errors
                    debug['backend']=requests.get(f'http://127.0.0.1:{port}/api/extension/jobs/{job_id}',params={'cvat_url':origin}).json()
                    (out/'debug.json').write_text(json.dumps(debug,ensure_ascii=False,indent=2),encoding='utf-8')
                    page.screenshot(path=str(out/'failure.png'))
                    raise
                panel=page.locator('#pointsnap-cvat-panel')
                panel.locator('[data-action=manual-rule]').first.click()
                page.wait_for_selector('#pointsnap-manual-hud',timeout=15000)
                page.wait_for_function("document.querySelectorAll('svg[data-pointsnap-view]').length===4")
                page.wait_for_selector('svg[data-pointsnap-view=side][data-rule=floating]',timeout=15000)
                report['browser']=context.browser.version
                check('four projected overlays and live HUD',True)
                check('no automatic repair controls',panel.locator('[data-action^="repair-"]').count()==0)
                check('guides do not write annotations',not writes and client.get_job_annotations(job_id)==before)
                for close in page.locator('.ant-notification-notice-close').all():
                    close.click()
                page.wait_for_timeout(200)
                page.screenshot(path=str(out/'manual-four-views.png'))
                # Each error on this same box changes the visual guide without changing geometry.
                for index,rule in [(1,'size.class_range'),(2,'heading.flip'),(3,'fit.outside'),(0,'floating')]:
                    panel.locator(f'[data-action=manual-rule][data-n="{index}"]').click()
                    page.wait_for_selector(f'svg[data-pointsnap-view=side][data-rule="{rule}"]',timeout=15000)
                check('all four error tools switch on the same box',client.get_job_annotations(job_id)==before)
                def selected():
                    return page.evaluate("""() => { const a=window.__manualTestStore.getState().annotation;
                        const r=a.canvas.instance.html().perspective.getDrawnObjects().find(r=>r.state.clientID===a.annotations.activatedStateID);
                        const m=r.cuboid.perspective;return {p:m.position.toArray(),s:m.scale.toArray(),r:[m.rotation.x,m.rotation.y,m.rotation.z]};} """)
                def point(view,which='center'):
                    return page.evaluate("""([view,which]) => {const a=window.__manualTestStore.getState().annotation,c=a.canvas.instance,v=c.view.views[view];
                        const r=c.html().perspective.getDrawnObjects().find(r=>r.state.clientID===a.annotations.activatedStateID);
                        const m=r.cuboid.perspective,b={center:m.position.toArray(),dims:m.scale.toArray(),rotation:[m.rotation.x,m.rotation.y,m.rotation.z]};
                        const q=which==='center'?b.center:which==='rotate'?r.cuboid.getRotationHelperPosition(view).toArray():r.cuboid.getResizeHelperPositions()[Number(which)].toArray();
                        const rect=v.renderer.domElement.getBoundingClientRect(),s=window.PointSnapGeometry.project(q,v.camera,rect);
                        return [rect.left+s[0],rect.top+s[1]];}""",[view,which])
                for view in ['top','side','front']:
                    page.wait_for_timeout(400);old=selected();x,y=point(view)
                    page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+22,y-14,steps=12);page.mouse.up();page.wait_for_timeout(350)
                    new=selected();check('native translation in '+view,old['p']!=new['p'])
                    check('HUD matches native coordinates in '+view,all(f'{v:.3f}' in page.locator('#pointsnap-manual-hud').inner_text() for v in new['p']))
                check('manual edits stay unsaved in CVAT memory',not writes and client.get_job_annotations(job_id)==before)
                # Resize via CVAT's native corner handle.
                old=selected();x,y=point('top','0');page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+16,y+10,steps=10);page.mouse.up();page.wait_for_timeout(400)
                check('native resize',selected()['s']!=old['s'])
                old=selected();x,y=point('top','rotate');page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+20,y+8,steps=10);page.mouse.up();page.wait_for_timeout(400)
                check('native yaw rotation',selected()['r']!=old['r'])
                old=selected();x,y=point('front','rotate');page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+18,y+8,steps=10);page.mouse.up();page.wait_for_timeout(400)
                check('native roll/pitch remains visible and is not auto-leveled',selected()['r']!=old['r'] and any(abs(v)>1e-6 for v in selected()['r'][:2]))
                page.wait_for_function("document.querySelector('#pointsnap-manual-hud')?.textContent.includes('roll/pitch')",timeout=15000)
                check('tilted draft is not certified by yaw-only rules',True)
                # Zoom each orthographic camera; overlays must survive and follow viewport dimensions.
                for view in ['top','side','front']:
                    x,y=point(view);page.mouse.move(x,y);page.mouse.wheel(0,-160);page.wait_for_timeout(100)
                page.set_viewport_size({'width':1450,'height':1000});page.wait_for_timeout(300)
                check('overlays survive zoom and resize',page.locator('svg[data-pointsnap-view]').count()==4)
                for key in ['reference','rulers','points']:
                    panel.locator(f'[data-action=manual-toggle][data-k={key}]').click()
                    panel.locator(f'[data-action=manual-toggle][data-k={key}]').click()
                check('guide toggles do not save geometry',not writes)
                stats=page.evaluate('window.PointSnapManualBridge.performanceStats()');report['overlay_render']=stats
                check('input to HUD DOM p95 <= 50 ms',stats['input_samples']>10 and stats['input_to_overlay_p95_ms']<=50)
                page.screenshot(path=str(out/'manual-after-drag.png'))
                # Undo/redo through actual CVAT keyboard bindings.
                old=selected();page.keyboard.press('Control+z');page.wait_for_timeout(400)
                check('native Undo updates geometry',selected()!=old)
                page.keyboard.press('Control+Shift+z');page.wait_for_timeout(400)
                check('native Redo updates geometry',selected()==old)
                # Native Save is the only annotation network write in the browser test.
                page.keyboard.press('Control+s');page.wait_for_timeout(2000)
                check('native Save writes annotations',bool(writes))
                check('Save removes stale guide identities',page.locator('svg[data-pointsnap-view][data-rule="floating"]').count()==0)
                frame_input=page.locator('.cvat-player-frame-selector input')
                frame_input.fill('1');frame_input.press('Enter')
                page.wait_for_function('window.__manualTestStore.getState().annotation.player.frame.number===1',timeout=15000)
                page.wait_for_timeout(500)
                check('frame navigation never reuses the previous reference',page.locator('svg[data-pointsnap-view][data-rule="floating"]').count()==0)
                frame_input.fill('0');frame_input.press('Enter')
                page.wait_for_function('window.__manualTestStore.getState().annotation.player.frame.number===0',timeout=15000)
                page.wait_for_timeout(350)
                check('returning to a saved frame does not reload old references',page.locator('svg[data-pointsnap-view][data-rule="floating"]').count()==0)
                check('no automatic repair API calls',not any('/apply-repair' in u or '/rollback' in u for u in writes))
                # The web side is advisory, with no old apply/rollback controls.
                web=context.new_page();web.goto(f'http://127.0.0.1:{port}/app#results')
                web.locator('#system-continue:not([disabled])').click(timeout=20000)
                web.wait_for_selector('#findings-table-body tr',timeout=20000)
                web.screenshot(path=str(out/'workspace-web.png'))
                web.locator('#detail-manual-status').filter(has_text='Cần quét lại sau Save').wait_for(timeout=3000)
                check('native Save state synchronizes from MV3 extension to web',True)
                check('web results remain readable without automatic repair buttons',web.locator('#btn-open-apply-repair, #btn-rollback-repair').count()==0)
                check('no extension JavaScript errors',not [e for e in errors if 'pointsnap' in e.lower()])
                report['page_errors']=errors
                context.close();context=None
        except Exception as exc:
            report['errors'].append(str(exc));traceback.print_exc()
            if context:
                try:context.pages[-1].screenshot(path=str(out/'failure.png'))
                except Exception:pass
        finally:
            if context:
                try:context.close()
                except Exception:pass
            if server:server.terminate();server.wait(timeout=10)
            if task_id:client.delete_task(task_id);report['temporary_task_deleted']=True
            (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            client.session.close()
    print(json.dumps({'checks':len(report['checks']),'errors':report['errors']},ensure_ascii=False))
    return bool(report['errors'])


if __name__=='__main__':raise SystemExit(main())
