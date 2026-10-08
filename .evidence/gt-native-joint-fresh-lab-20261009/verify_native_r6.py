import psycopg,tempfile,json,hashlib,sys
from pathlib import Path
from datetime import datetime,timezone
from psycopg.rows import dict_row
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
repo=Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo/'services/aos-api'))
from aos_api.aip_provider_capacity_publication_contracts import PublishedProviderCapacitySourceV2,parse_signed_capacity_body
base=repo/'.evidence/gt-atomic-model-admission-20261008';inp=json.loads((base/'source-joint-fresh-lab-r6-input.json').read_text());ref=inp['source_ref']
with psycopg.connect(host='127.0.0.1',port=5435,user='aos_app',dbname='aos_test_f70639ea0633_ti4_test',passfile='/Users/ddt/.aos-lab-secrets/aos-native-joint-memory-20261009/pgpass',row_factory=dict_row) as c:
 c.execute('SET TRANSACTION READ ONLY');assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']=='7694371626696531992'
 row=c.execute('SELECT asset_id,revision,content_hash,source_raw,signature,account_id,attempt_id FROM aos_capacity_publication_private.source_publication WHERE org_id=%s AND project_id=%s AND asset_id=%s AND revision=%s',('org-org','dev-project',ref['assetId'],ref['revision'])).fetchone();assert row and row['content_hash']==ref['contentHash']
 raw=bytes(row['source_raw']);source=parse_signed_capacity_body(raw,PublishedProviderCapacitySourceV2);assert source.model_dump(mode='json',by_alias=True)==inp['source'];assert hashlib.sha256(raw).hexdigest()==row['content_hash']
 keys=c.execute('SELECT public_key,publisher_literal,key_id_literal FROM aos_capacity_publication_private.root_entry WHERE publisher_codepoints=%s::integer[] AND key_id_codepoints=%s::integer[]',([ord(x) for x in source.publisher],[ord(x) for x in source.key_id])).fetchall();assert len(keys)==1
 assert json.loads(keys[0]['publisher_literal'])==source.publisher and json.loads(keys[0]['key_id_literal'])==source.key_id
 Ed25519PublicKey.from_public_bytes(bytes(keys[0]['public_key'])).verify(bytes(row['signature']),raw)
 now=c.execute('SELECT clock_timestamp() AS now').fetchone()['now'];assert c.execute('SELECT count(*) AS n FROM aos_capacity_publication_private.registry_epoch').fetchone()['n']==1
 assert c.execute('SELECT count(*) AS n FROM aos_capacity_publication_private.source_publication').fetchone()['n']==1
 roles=c.execute("SELECT rolname,rolcanlogin,rolsuper FROM pg_roles WHERE rolname IN ('aos_provider_capacity_issuer','aos_provider_capacity_occupation') ORDER BY rolname").fetchall();assert len(roles)==2 and all(x['rolcanlogin'] is False and x['rolsuper'] is False for x in roles)
 other=c.execute("SELECT count(*) AS n FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND state<>'idle'").fetchone()['n'];assert other==0
 debit=json.loads((base/'source-joint-fresh-lab-r6-parent-debit.json').read_text());assert debit['commit_sqlstate']=='23514' and debit['private_rows']==0 and debit['caller_status']=='aborted'
 whole=json.loads((base/'source-joint-fresh-lab-r6-whole-source-plan-verification.json').read_text());assert whole['cases']==2 and whole['legs']==4 and whole['execution_allowed'] is False
 assert all(whole['caller'][k]==inp['caller'][k] for k in ('xid','pid'))
 proof={'observed_at':datetime.now(timezone.utc).isoformat(),'database':'aos_test_f70639ea0633_ti4_test','readonly':True,'source_ref':ref,'source_raw_sha256':hashlib.sha256(raw).hexdigest(),'source_signature_matches_original_registered_key':True,'registry_count':1,'publication_count':1,'same_caller':whole['caller'],'cases':2,'legs':4,'physical_debit_commit_rejected':debit['commit_sqlstate'],'debit_private_rows_after_abort':0,'roles_closed':roles,'other_active_sessions':other,'source_valid_until':source.valid_until.isoformat(),'source_in_half_open_window_at_read':source.valid_from<=now<source.valid_until,'scope':'original old-purpose isolated Source/physical boundary only; newJudge whole joint and real firstchain pending'}
(Path(__file__).resolve().parent/'native-r6-independent.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n');print(json.dumps(proof,ensure_ascii=False))
