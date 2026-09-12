import json
import os
import subprocess

r = os.environ['REPO']
for wf in ['continuous-collector.yml', 'process-batch.yml', 'storage-housekeeping.yml']:
    x = json.loads(
        subprocess.check_output(
            ['gh', 'api', f'repos/{r}/actions/workflows/{wf}'],
            text=True,
        )
    )
    print(wf, x['state'], x['id'])
