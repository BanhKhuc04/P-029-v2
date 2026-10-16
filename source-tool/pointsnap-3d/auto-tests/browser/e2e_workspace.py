"""UI contract against demo_server (8767): startup, stable identities, events and responsive themes."""
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

base=sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8767'
out=Path('out/workspace-v3');out.mkdir(parents=True,exist_ok=True)
checks=[]


def check(name,value):
    assert value,name
    checks.append(name)
    print('PASS',name,flush=True)


with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    runs=page.request.get(base+'/api/projects/demo/scans').json()
    run=page.request.get(base+'/api/projects/demo/scans/'+runs[0]['run_id']).json()
    visible=[f for f in run['findings'] if f['actionable']]
    target=next(f for f in visible if f['error_type']=='size')
    page.request.put(base+f"/api/projects/demo/scans/{run['run_id']}/reviews/{target['finding_index']}",data={'verdict':None})
    page.goto(base+'/app#results')
    page.locator('#system-continue:not([disabled])').wait_for()
    check('startup checks environment even with existing scans',page.locator('#tab-system').is_visible())
    check('missing required models block scanning',page.locator('#btn-start-scan').is_disabled())
    check('models show actual Python installation instructions','Scripts\\python.exe' in page.locator('#system-checks').inner_text())
    page.screenshot(path=str(out/'system-light.png'))
    page.locator('#system-continue').click()
    page.locator('#findings-table-body tr.selected').wait_for()
    check('old results remain accessible',page.locator('#results-content-box').is_visible())
    check('information severity controls removed',page.locator('#sev-tab-info,#stat-info-count').count()==0)
    check('scan diagnostics retained separately',page.locator('#scan-diagnostics').is_visible())
    page.select_option('#filter-error-type','size')
    page.locator('#findings-table-body tr').first.click()
    check('filtered selection preserves original frame',page.locator('#detail-frame-val').inner_text()=='#'+str(target['frame']))
    page.locator('#btn-review-ok').click()
    page.wait_for_timeout(500)
    reviews=page.request.get(base+f"/api/projects/demo/scans/{run['run_id']}/reviews").json()['reviews']
    check('review stored at original finding index',reviews.get(str(target['finding_index']))=='ok')
    page.select_option('#filter-error-type','')
    event={'slug':'demo','run_id':run['run_id'],'job_id':run['job_id'],'cvat_url':'http://localhost:8080',
           'finding_index':target['finding_index'],'kind':'evaluated','state':'cleared','revision':9,'session':'workspace-e2e-'+str(time.time_ns()),'sequence':1}
    start=time.perf_counter();res=page.request.post(base+'/api/extension/events',data=event)
    check('manual events accepted for exact scope',res.ok)
    page.locator('#detail-manual-status').filter(has_text='Hết lỗi đang xét — chưa Save').wait_for(timeout=3000)
    elapsed=(time.perf_counter()-start)*1000
    check('manual state synchronized within 3 seconds',elapsed<=3000)
    event.update(sequence=3,kind='saved',state='stale')
    page.request.post(base+'/api/extension/events',data=event)
    page.locator('#detail-manual-status').filter(has_text='Cần quét lại sau Save').wait_for(timeout=3000)
    event.update(sequence=2,kind='evaluated',state='cleared')
    check('out of order evaluation cannot replace Save',not page.request.post(base+'/api/extension/events',data=event).json()['accepted'])
    page.wait_for_timeout(1000)
    check('Save invalidation remains visible','Cần quét lại' in page.locator('#detail-manual-status').inner_text())
    for width in (1920,1440,1280,768):
        page.set_viewport_size({'width':width,'height':1000})
        for theme in ('light','dark'):
            page.locator('#theme-btn-'+theme).click()
            page.evaluate('window.scrollTo(0,0)')
            page.wait_for_timeout(300)
            check(f'{width} {theme}: no horizontal overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
            if width>=1280:
                a=page.locator('.findings-list-panel').bounding_box();b=page.locator('.detail-drawer-panel').bounding_box()
                check(f'{width} {theme}: panel alignment',abs(a['height']-b['height'])<=1 and abs(a['y']-b['y'])<=1)
                check(f'{width} {theme}: panels fit viewport',a['y']+a['height']<=1000)
            page.screenshot(path=str(out/f'results-{width}-{theme}.png'))
    page.set_viewport_size({'width':1440,'height':1000})
    for theme in ('light','dark'):
        page.locator('#theme-btn-'+theme).click()
        page.wait_for_timeout(400)
        page.screenshot(path=str(Path('landing/assets')/f'workspace-{theme}.png'))
    page.locator('[data-tab="tab-system"]').click()
    page.select_option('#system-camera-mode','false')
    with page.expect_response(lambda r:r.request.method=='PUT' and r.url.endswith('/guideline')) as saved:
        page.locator('#system-save-camera').click()
    assert saved.value.ok
    page.wait_for_function("document.querySelector('#system-camera-mode')?.value==='false' && !document.querySelector('#system-recheck').disabled")
    check('camera mode is saved through the UI',page.request.get(base+'/api/projects/demo/guideline').json()['config']['camera']['enabled']=='false')
    check('disabling optional camera does not fake CVAT readiness',page.locator('#btn-start-scan').is_disabled())
    check('no JavaScript errors',not errors)
    browser.close()
(out/'ui-report.json').write_text(json.dumps({'checks':checks,'sync_ms':elapsed,'errors':errors},indent=2,ensure_ascii=False),encoding='utf-8')
print(f'{len(checks)}/{len(checks)} PASS')
