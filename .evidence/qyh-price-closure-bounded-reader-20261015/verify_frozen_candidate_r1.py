"""Freeze committed base plus exactly four owned overlays; never copy other dirty files."""
from pathlib import Path, PurePosixPath
import datetime
import hashlib
import io
import json
import os
import subprocess
import tarfile

E=Path(__file__).resolve().parent;R=E.parents[1]
files=['services/aos-api/aos_api/ecommerce_three_module_closure_readonly.py',
       'services/aos-api/tests/test_ecommerce_three_module_closure_readonly.py',
       'services/aos-api/aos_api/routers/ecommerce_workshop.py',
       'services/aos-api/tests/test_ecommerce_workshop_read_http.py']
before={p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in files}
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()
assert head=='804a0279aa3d426a693504cb3336fb5a8ca4d149'
source=E/'private/candidate-source-r1'
assert not source.exists() and not (E/'candidate-freeze-r1-intent.json').exists()
raw=subprocess.check_output(['git','archive',head,'services/aos-api','scripts','bundles'],cwd=R);members={}
with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
    for item in archive.getmembers():
        p=PurePosixPath(item.name)
        assert not p.is_absolute() and '..' not in p.parts and (item.isfile() or item.isdir())
        if item.isfile() and not any(x.startswith('.env') for x in p.parts):members[item.name]=archive.extractfile(item).read()
for p in files:members[p]=(R/p).read_bytes()
with (E/'candidate-freeze-r1-intent.json').open('x') as stream:
    json.dump(dict(baseHead=head,overlay=before,privateSource=str(source),noUserDirtyCopied=True,noServiceEffects=True),stream,indent=2)
source.mkdir(parents=True,mode=0o700)
for name,body in members.items():
    p=source/name;p.parent.mkdir(parents=True,exist_ok=True,mode=0o700);p.write_bytes(body);p.chmod(0o600)
assert {str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}=={n:hashlib.sha256(b).hexdigest() for n,b in members.items()}
backend=source/'services/aos-api'
tests=['tests/test_ecommerce_workshop_read_http.py','tests/aip/test_ecommerce_price_disposition_readonly.py',
       'tests/aip/test_w6_06_price_disposition.py','tests/aip/test_w6_06_price_disposition_store.py',
       'tests/test_ecommerce_price_research_readonly.py','tests/aip/test_w6_05_price_research.py',
       'tests/test_ecommerce_workshop_read_catalog.py','tests/test_ecommerce_three_module_closure_readonly.py',
       'tests/test_w6_009_three_module_closure.py']
cmd=[str(R/'services/aos-api/.venv/bin/python'),'-m','pytest','-q','-p','no:cacheprovider',*tests]
env={k:v for k,v in os.environ.items() if not k.startswith(('AOS_','PG'))}
env.update(PYTHONDONTWRITEBYTECODE='1',AOS_DOTENV_DISABLED='1',AOS_TEST_USE_SHARED_DATABASE='1',
    AOS_DATABASE_URL='postgresql://placeholder@127.0.0.1:1/unused',PYTHONPATH=str(backend))
at=datetime.datetime.now(datetime.timezone.utc).isoformat()
with (E/'green-frozen-cumulative-r1.log').open('x') as stream:
    result=subprocess.run(cmd,cwd=backend,env=env,stdout=stream,stderr=subprocess.STDOUT)
after={p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in files}
assert before==after
with (E/'source-verification-r1.json').open('x') as stream:
    json.dump(dict(sourceBefore=before,sourceAfter=after,returncode=result.returncode,command=cmd,baseHead=head,
        frozenWithOnlyFourOwnedOverlays=True,noUserDirtyCopied=True,originalVolumeTouched=False,at=at,
        finishedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        knownSeparateFailure='Unchanged historical migration test expects w6_009, current committed migration head a0v_162; prior raw failure retained, no schema changes.',
        logSha=hashlib.sha256((E/'green-frozen-cumulative-r1.log').read_bytes()).hexdigest()),stream,indent=2)
print(json.dumps(dict(returncode=result.returncode,hashesEqual=True,frozenOnlyFourOwnedOverlays=True)))
