#!/usr/bin/env python3
"""Nightly end-to-end health check for the Futures research pipeline."""
import json, os, subprocess, sys, time

repo=os.environ.get('REPO')
if not repo:
    raise SystemExit('REPO is required')

def api(path):
    return json.loads(subprocess.check_output(['gh','api',path], text=True))

workflows=['continuous-collector.yml','process-batch.yml','storage-housekeeping.yml']
errors=[]
for wf in workflows:
    data=api(f'repos/{repo}/actions/workflows/{wf}/runs?branch=main&per_page=20')
    runs=data.get('workflow_runs',[])
    active=[r for r in runs if r.get('status') in ('queued','in_progress')]
    recent=[r for r in runs if time.time()-time.mktime(time.strptime(r['created_at'][:19],'%Y-%m-%dT%H:%M:%S')) <= 8*3600]
    print(wf, 'recent=', len(recent), 'active=', len(active))
    if any(r.get('conclusion')=='failure' for r in recent): errors.append(f'{wf}: failure')

collectors=api(f'repos/{repo}/actions/workflows/continuous-collector.yml/runs?branch=main&per_page=20')['workflow_runs']
processors=api(f'repos/{repo}/actions/workflows/process-batch.yml/runs?branch=main&per_page=100')['workflow_runs']
for r in collectors:
    if r.get('conclusion')!='success': continue
    arts=api(f"repos/{repo}/actions/runs/{r['id']}/artifacts?per_page=100")['artifacts']
    raws=[a for a in arts if a['name'].startswith('coindcx-futures-raw-')]
    if len(raws)!=1:
        errors.append(f"collector {r['id']}: expected 1 Futures raw artifact, found {len(raws)}")
        continue
    batch=raws[0]['name'].replace('coindcx-futures-raw-','',1)
    matches=[p for p in processors if batch in (p.get('name') or '')]
    print('batch',batch,'processor_matches',len(matches))
    if not matches:
        print('MISSING_PROCESSOR', batch)

if errors:
    print('HEALTH FAIL')
    print(*errors,sep='\n')
    sys.exit(1)
print('HEALTH PASS')
