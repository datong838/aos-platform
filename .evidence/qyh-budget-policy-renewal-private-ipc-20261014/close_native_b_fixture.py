"""Read back exact owned tmpfs fixture and stop it, never touch named volumes."""
from pathlib import Path
import json,subprocess,sys
import psycopg
P=Path(__file__).resolve().parent
attempt=sys.argv[1]
assert attempt in {'r2','r3','r4'}
r=json.loads((P/f'native-b-fixture-ready-{attempt}.json').read_text())
m=json.loads((P/f'native-b-migration-ready-{attempt}.json').read_text())
d=['docker','--context','colima-aos-extension']
info=json.loads(subprocess.check_output(d+['inspect',r['cid']],text=True))[0]
assert info['State']['Running'] and info['Config']['Labels']['aos.owner']==r['owner']
assert len(info['Mounts'])==1 and info['Mounts'][0]['Type']=='tmpfs' and not (P/f'native-b-fixture-stop-intent-{attempt}.json').exists()
with psycopg.connect(host='127.0.0.1',port=r['port'],dbname=m['database'],user='aos_app') as conn:
 conn.execute('SET TRANSACTION READ ONLY')
 counts=conn.execute('SELECT (SELECT count(*) FROM public.aip_budget_policy_renewal_proposal),(SELECT count(*) FROM public.aip_budget_policy_renewal_decision),(SELECT count(*) FROM public.aip_budget_policy_renewal_receipt),(SELECT count(*) FROM public.aip_model_governance_policy_revision)').fetchone()
 head=conn.execute('SELECT current_revision,version FROM public.aip_model_governance_policy_head').fetchone()
 roles=conn.execute("SELECT rolname,rolcanlogin FROM pg_roles WHERE rolname LIKE 'aos_budget_renewal_%' ORDER BY rolname").fetchall()
 triggers=conn.execute("""SELECT tgname,tgenabled FROM pg_trigger WHERE
  (tgname='aip_budget_active_insert_guard' AND tgrelid='public.aip_budget_revision'::regclass)
  OR (tgname='cost_configuration_write_guard' AND tgrelid='public.aip_model_governance_policy_revision'::regclass)
  ORDER BY tgname""").fetchall()
 assert counts==(2,2,5,2) and head==(14,14) and len(roles)==6 and all(not x[1] for x in roles)
 assert len(triggers)==2 and all(x[1]=='O' for x in triggers)
(P/f'native-b-final-readback-{attempt}.json').write_text(json.dumps({'fixtureCid':r['cid'],'countsProposalDecisionReceiptCanonical':counts,'head':head,'allSixNoLogin':True,'originalGuardsRestored':triggers,'extraLostAckProposalOnlyPrepared':True,'noRealConsent':True,'originalVolumeTouched':False},indent=2))
(P/f'native-b-fixture-stop-intent-{attempt}.json').write_text(json.dumps({'cid':r['cid'],'owner':r['owner'],'readbackComplete':True}))
subprocess.check_call(d+['stop',r['cid']],stdout=subprocess.DEVNULL)
state=json.loads(subprocess.check_output(d+['inspect',r['cid']],text=True))[0]['State'];assert not state['Running']
(P/f'native-b-fixture-stopped-{attempt}.json').write_text(json.dumps({'cid':r['cid'],'state':state,'originalVolumeTouched':False},indent=2))
print(json.dumps({'stoppedFixture':attempt,'readbackMatched':True,'originalVolumeTouched':False}))
