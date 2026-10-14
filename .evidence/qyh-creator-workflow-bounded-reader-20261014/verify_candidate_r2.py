from pathlib import Path
import datetime,hashlib,json,os,subprocess
Q=Path(__file__).resolve().parent;R=Q.parents[1]
files=['services/aos-api/aos_api/ecommerce_creator_internal_workflow_readonly.py','services/aos-api/tests/test_ecommerce_creator_internal_workflow_readonly.py']
def hashes():return {p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in files}
before=hashes();at=datetime.datetime.now(datetime.timezone.utc).isoformat()
cmd=[str(R/'services/aos-api/.venv/bin/python'),'-m','pytest','-p','no:cacheprovider',*['services/aos-api/tests/'+p for p in ['test_ecommerce_creator_internal_workflow_readonly.py','test_ecommerce_creator_internal_workflow.py','test_ecommerce_workshop_read_catalog.py','test_ecommerce_workshop_read_http.py']]]
with (Q/'green-source-r2.log').open('x') as out:
 r=subprocess.run(cmd,cwd=R,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','AOS_TEST_USE_SHARED_DATABASE':'1','AOS_DATABASE_URL':'postgresql://placeholder@127.0.0.1:1/unused','AOS_DOTENV_DISABLED':'1'},stdout=out,stderr=subprocess.STDOUT)
after=hashes();assert before==after
(Q/'verification-source-r2.json').write_text(json.dumps({'at':at,'finishedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'command':cmd,'returncode':r.returncode,'sourceBefore':before,'sourceAfter':after,'logSha256':hashlib.sha256((Q/'green-source-r2.log').read_bytes()).hexdigest(),'originalRuntimeTouched':False,'uncommittedCandidate':True},indent=2));assert r.returncode==0
print({'sourceEqual':before==after,'returncode':r.returncode})
