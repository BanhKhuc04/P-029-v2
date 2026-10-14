"""Audit the original 131-file scope against a chosen candidate, with per-file conclusions."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote

p = argparse.ArgumentParser()
p.add_argument('--repo',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a = p.parse_args()
repo = a.repo.resolve()
scope = repo/'review/2026-10-13/scope-inventory.tsv'
rows = list(csv.DictReader(scope.open(encoding='utf-8-sig',newline=''),delimiter='\t'))
assert len(rows)==131 and len({r['path'] for r in rows})==131
results=[]
for r in rows:
    path=repo/r['path']; owner=r['owner']; exists=path.is_file()
    item={'path':r['path'],'owner':owner,'status':r['status'],'exists':exists,'links_missing':[]}
    if exists:
        raw=path.read_bytes(); item['sha256']=hashlib.sha256(raw).hexdigest(); item['bytes']=len(raw)
        if path.suffix.lower()=='.md':
            text=raw.decode('utf-8-sig')
            for link in re.findall(r'\]\(([^\s)]+)(?:\s+[^)]*)?\)',text):
                target=unquote(link.strip('<>').split('#')[0])
                if target and not re.match(r'^(?:https?:|mailto:|codex:|data:|[A-Za-z]:)',target):
                    if not (path.parent/target).exists():item['links_missing'].append(target)
            item['conclusion']='Historical document; paths audited, claims remain tied to its stated date/source. Current acceptance: 16-report.md.'
        elif path.suffix.lower() in ('.png','.jpg','.jpeg'):
            item['conclusion']='Historical illustration retained; file hash recorded. Not a current benchmark or UI acceptance screenshot.'
        elif owner=='14':
            item['conclusion']='Integration regression suites and real CLI/Web/API geometry parity; installed MV3 acceptance remains partial. See 14-report.md.'
        elif owner=='15':
            item['conclusion']='Evaluation metric/split regression coverage; human precision and long vision/OOM remain unassessed. See 15-report.md.'
        else:
            item['conclusion']='Covered by owner '+owner+' report and handoff regression suites; model/data limits are retained.'
    else:
        item['conclusion']='Expected deletion/rename; retained in historical inventory, not a missing runtime module.' if r['status'].startswith(('D','R')) else 'Missing unexpected file: investigate.'
    if r['path'].endswith('pyproject.toml'):
        item['conclusion']='Clean wheel/sdist install and Linux base container verified; Windows GPU vision smoke verified; no fresh CPU vision installation claim.'
    results.append(item)
data={'model':'gpt-6.1-sol','source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo).decode().strip(),
      'files':results,'scope':'Per-file structural audit and owner evidence references; not 131 fresh independent deep reviews or visual reproduction of historical figures.'}
a.out.parent.mkdir(parents=True,exist_ok=True)
a.out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({'files':len(results),'missing_files':[r['path'] for r in results if not r['exists']],
                 'broken_links':[{k:r[k] for k in ('path','links_missing')} for r in results if r['links_missing']]},ensure_ascii=False,indent=2))
