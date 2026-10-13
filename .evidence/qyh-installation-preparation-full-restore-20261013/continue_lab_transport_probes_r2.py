"""Continue only never-run readonly probes after internal-network tunnel reconciliation."""
from pathlib import Path
import runpy,json,sys,os
P=Path(__file__).resolve().parent;N=runpy.run_path(str(P/'restore.py'),run_name='probe_baseline');b=N['b']
os.environ['AOS_DOTENV_DISABLED']='1';sys.path.insert(0,str(N['ROOT']/'services/aos-api'))
import psycopg
from psycopg.rows import dict_row
from psycopg.conninfo import make_conninfo
from aos_api.extension_runtime.runtime_identity import probe_runtime_database_identity,require_isolated_runtime_identities
from aos_api.extension_runtime.production_runtime import _PROTECTED_RELATIONS
from aos_api.extension_runtime.runtime_connections import _runtime_file_dsns
if __name__=='__main__':
 intent=json.loads((P/'lab-tunnel-intent.json').read_text());name=P.name+'-transport'
 clone=json.loads(b.docker('inspect',name,text=True,capture_output=True).stdout)[0]
 assert clone['Id']==intent['container'] and clone['State']['Running'] and clone['Mounts'][0]['Name']==P.name
 identities=json.loads((P/'private/lab-identities.json').read_text());checked={}
 for plane,item in identities.items():
  with psycopg.connect(item['dsn'],row_factory=dict_row,connect_timeout=5) as conn:
   if plane=='directory':conn.read_only=True
   checked[plane]=probe_runtime_database_identity(conn,protected_relations=_PROTECTED_RELATIONS)
 require_isolated_runtime_identities(**checked)
 for plane,item in identities.items():
  try:psycopg.connect(make_conninfo(item['dsn'],password='KnownNegativeWrongLabSecret'),connect_timeout=5)
  except psycopg.OperationalError:pass
  else:raise AssertionError('wrong lab secret admitted')
 _runtime_file_dsns(str((P/'private/lab-identities.json').resolve()))
 before=json.loads((P/'source-before.json').read_text())
 assert b.fingerprint(name,'aos_meta_head')==before['fingerprints']
 clone_meta=b.metadata(name,'aos_meta_head');original_meta=before['metadata']
 assert all(clone_meta[k]==original_meta[k] for k in ('roles','sequences','sequenceStates'))
 expected=json.loads((P/'review-supplement.json').read_text())
 assert clone_meta['schemaSHA256']==expected['cloneSchemaSHA256']
 assert b.fingerprint(b.SOURCE,'aos_meta_head')==before['fingerprints'] and b.metadata(b.SOURCE,'aos_meta_head')==before['metadata']
 with (P/'lab-transport-verification.json').open('x') as f:json.dump({'outcome':'REAL_ISOLATED_THREE_PLANE_LAB_TRANSPORT_GREEN','container':clone['Id'],'volume':P.name,'internalNetwork':intent['internalNetwork'],'loopbackPort':18549,'transport':'owned local SSH tunnel to internal exact clone','allThreeOriginalPhysicalIdentityProbesPassed':True,'allThreeWrongPasswordRejected':True,'lab650TablesMetadataUnchanged':True,'current650TablesMetadataUnchanged':True,'newGrants':False,'currentDatabaseWrites':False,'runtimeOperationRequested':False,'hostStarted':False,'eightPagesAccepted':False},f,indent=2)
 print('REAL_ISOLATED_THREE_PLANE_LAB_TRANSPORT_GREEN',flush=True)
