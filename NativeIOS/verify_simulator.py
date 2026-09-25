import json
import subprocess
import time
import urllib.request
from pathlib import Path

def run(*args):
    return subprocess.check_output(args, text=True).strip()

devices = json.loads(run('xcrun','simctl','list','devices','available','--json'))
device = next(d for group in devices['devices'].values() for d in group if 'iPad' in d['name'])
udid = device['udid']
subprocess.run(['xcrun','simctl','boot',udid], check=False)
subprocess.run(['xcrun','simctl','bootstatus',udid,'-b'], check=True)
simapp = 'build/simulator/Build/Products/Debug-iphonesimulator/IELTSStudy.app'
# Simulator executables still need a local ad-hoc signature. This is not an
# Apple device provisioning identity and is never substituted for IPA signing.
run('codesign','--force','--sign','-','--timestamp=none',simapp)
run('xcrun','simctl','install',udid,simapp)
artifact = Path('../artifacts/ios')
artifact.mkdir(parents=True, exist_ok=True)
for phase in ['cold-start', 'restart']:
    try:
        run('xcrun','simctl','launch',udid,'app.ielts.ieltsstudy','--offline-smoke-test')
    except subprocess.CalledProcessError:
        subprocess.run(['xcrun','simctl','spawn',udid,'log','show','--last','1m','--predicate','process == "IELTSStudy" OR eventMessage CONTAINS "app.ielts.ieltsstudy"'], check=False)
        raise
    container = Path(run('xcrun','simctl','get_app_container',udid,'app.ielts.ieltsstudy','data'))
    result = container / 'Documents/offline-smoke.json'
    deadline = time.monotonic() + 120
    while not result.exists() and time.monotonic() < deadline:
        time.sleep(2)
    run('xcrun','simctl','io',udid,'screenshot',str(artifact / f'ipad-{phase}.png'))
    if not result.exists():
        stage = container / 'Documents/native-stage.txt'
        print('Native stage:', stage.read_text() if stage.exists() else 'no stage', flush=True)
        try:
            with urllib.request.urlopen('http://127.0.0.1:18761/index.html', timeout=10) as response:
                print('Loopback HTTP:', response.status, response.read(100), flush=True)
        except Exception as e: print('Loopback HTTP:', repr(e), flush=True)
        subprocess.run(['xcrun','simctl','spawn',udid,'log','show','--last','3m','--predicate','process == "IELTSStudy"'], stdout=(artifact/'native-runtime.log').open('w'), timeout=30)
        raise AssertionError('WebKit smoke test timed out')
    report = json.loads(result.read_text())
    (artifact / f'{phase}.json').write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(phase, json.dumps(report, ensure_ascii=False))
    assert report.get('passed'), 'Offline learning smoke failed'
    assert list((container / 'Documents/Exports').glob('*native-backup-test.json')), 'Native Blob export missing'
    if phase == 'restart':
        assert report.get('restartPersistence'), 'WKWebsiteDataStore did not persist'
        assert report.get('answerRestored'), 'Actual saved answer did not restore'
    run('xcrun','simctl','terminate',udid,'app.ielts.ieltsstudy')
    result.unlink()
print('Offline native iPad startup, range playback reads, answer restart restore and Blob export passed')
