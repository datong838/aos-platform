"""Stop only the two exact owned rendering fixture processes."""
from pathlib import Path
import json, os, signal, subprocess, time
R=Path.cwd();E=R/'.evidence/qyh-price-visual-filter-sizing-20261015'
for variant in ['baseline','candidate']:
    row=json.loads((E/(variant+'-server-started-r2.json')).read_text())
    assert row['owner']=='codex-01a13484-f019-7d82-94ce-812396db9124'
    pid,port=row['pid'],row['port']
    actual=subprocess.check_output(['lsof','-t',f'-iTCP:{port}','-sTCP:LISTEN'],text=True).strip()
    assert actual==str(pid)
    command=subprocess.check_output(['ps','-p',str(pid),'-o','command='],text=True)
    assert 'fixture_server_r2.mjs '+variant in command
    path=E/(variant+'-stop-intent-r1.json')
    with path.open('x') as f:json.dump({'pid':pid,'port':port,'owner':row['owner'],'fixtureOnly':True},f);f.flush();os.fsync(f.fileno())
    os.kill(pid,signal.SIGTERM)
    for _ in range(100):
        observed=subprocess.run(['lsof','-t',f'-iTCP:{port}','-sTCP:LISTEN'],capture_output=True,text=True)
        if not observed.stdout.strip():break
        time.sleep(.1)
    else:raise RuntimeError('Stop unresolved; reconcile without replay')
    with (E/(variant+'-stopped-r1.json')).open('x') as f:json.dump({'pid':pid,'port':port,'portFree':True,'originalServicesTouched':False},f)
print('Both exact owned fixture ports free; original services untouched')
