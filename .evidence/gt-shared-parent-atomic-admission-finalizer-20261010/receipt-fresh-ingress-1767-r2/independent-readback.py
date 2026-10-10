"""Reconcile retained native attempt only; no application replay."""
import pathlib,json,psycopg,hashlib,re,base64
from psycopg.rows import dict_row
from psycopg import sql
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from aos_api import aip_provider_capacity_catalog_audit_profile as cat,aip_shared_parent_atomic_admission as api
from aos_api.aip_model_runtime_store import canonical_hash
b=pathlib.Path(__file__).resolve().parent;r=b.parents[2]
lab=json.loads((r/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text());db=json.loads((b/'result-r2.json').read_text())['databases'][0]
proof=json.loads((b/'parent-risk-stage-proof.json').read_text());positive=json.loads((b/'receipt-v2-positive-proof.json').read_text());late=json.loads((b/'receipt-v2-late-writer-proof.json').read_text());component=json.loads((b/'component-native-proof.json').read_text());auth=json.loads((b/'fresh-ingress-authentication.json').read_text());receipt=positive['receipt'];body=receipt['immutable'];facts=body['physicalFacts']
assert receipt['contentHash']=='sha256:'+canonical_hash(body)
assert len(body['nodes'])==8 and body['sourcePacketHash']=='sha256:'+auth['fresh_packet_sha256']
assert facts['unresolvedRequests']==len(facts['unresolvedMembers'])==2 and facts['unresolvedTokenUpperBound']==20000
assert positive['physical']['physicalComparisonMatched'] and late['final_physical_changed_rejected'] and late['actual_union']=={'requests':3,'tokens':30000}
assert component['actual_commit_rejected'] and component['rollback_xid']==proof['caller']['xid']==body['callerXid']
key=Ed25519PublicKey.from_public_bytes(base64.b64decode(proof['root']['publicKeyBase64']))
for e in proof['certificates']:
    raw=json.dumps(e['certificate'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    key.verify(base64.b64decode(e['signatureBase64']),b'AOS-MODEL-EVAL-SHARED-PARENT-CERTIFICATE-SIGNING-INPUT-v3\n'+raw)
assert len(proof['certificates'])==4
statements=(*api.shared_parent_exact_receipt_statements(),*api.shared_parent_final_physical_comparison_statements())
with psycopg.connect(host='127.0.0.1',port=lab['port'],user='aos_app',dbname=db,passfile=lab['passfile'],row_factory=dict_row) as c:
    c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
    out={'database':db,'cluster':c.execute('SELECT system_identifier::text id FROM pg_control_system()').fetchone()['id'],'caller_state':c.execute('SELECT pg_xact_status(%s::xid8) state',(proof['caller']['xid'],)).fetchone()['state'],'other_backends':c.execute('SELECT count(*) n FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()').fetchone()['n'],'shared_rows':{},'parent_reservations':{}}
    for row in c.execute("SELECT n.nspname,c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname LIKE 'aos_shared_parent%' AND c.relkind='r'").fetchall():
        out['shared_rows'][row['nspname']+'.'+row['relname']]=c.execute(sql.SQL('SELECT count(*) n FROM {}.{}').format(sql.Identifier(row['nspname']),sql.Identifier(row['relname']))).fetchone()['n']
    original=proof['risk']['immutable']['originalRisk']['originalFacts']
    for purpose,table in [('target','aip_model_eval_budget_reservation'),('judge','aip_model_judge_budget_reservation')]:
        out['parent_reservations'][purpose]=c.execute(sql.SQL('SELECT count(*) n FROM {} WHERE reservation_id=%s').format(sql.Identifier(table)),(original[purpose]['reservationId'],)).fetchone()['n']
    out['catalog_profile_installed']=cat.catalog_profile_is_installed(c)
    out['fact_original_exact']=c.execute('SELECT prosrc FROM pg_proc WHERE oid=%s::regprocedure',(cat.FACT,)).fetchone()['prosrc']==cat.epoch._body(cat.store.CAPACITY_ORIGINAL_WITHDRAWAL_BOUNDARY_SQL,cat.FACT)
    out['roles']=c.execute("SELECT rolname,rolcanlogin,rolinherit,rolsuper,rolcreaterole,rolbypassrls FROM pg_roles WHERE rolname IN ('aos_provider_capacity_issuer','aos_provider_capacity_occupation','aos_capacity_publication_owner','aos_model_eval_issuer_owner')").fetchall()
    source=c.execute('SELECT content_hash,source_raw,signature FROM aos_capacity_publication_private.source_publication').fetchall()
    assert len(source)==1 and hashlib.sha256(bytes(source[0]['source_raw'])).hexdigest()==source[0]['content_hash']
    assert facts['sourceRef']['contentHash']==source[0]['content_hash']
    out.update(source_publication_count=1,source_hash=source[0]['content_hash'],source_signature_bytes=len(source[0]['signature']))
    out['native_receipt_functions']=[]
    for statement in statements:
        match=re.search(r'CREATE (?:OR REPLACE )?FUNCTION ([\w.]+)\(.*?AS \$(\w+)\$(.*?)\$\2\$',statement,re.S)
        if not match:continue
        name,tag,expected=match.groups();n,f=name.split('.')
        owner=re.search(r'ALTER FUNCTION '+re.escape(name)+r'\([^)]*\) OWNER TO (\w+)', '\n'.join(statements)).group(1)
        row=c.execute('SELECT p.prosrc,pg_get_userbyid(p.proowner) owner,p.proconfig,p.prosecdef FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname=%s AND p.proname=%s',(n,f)).fetchone()
        assert row and row['prosrc']==expected and row['owner']==owner and row['proconfig']==['search_path=pg_catalog']
        out['native_receipt_functions'].append({'name':name,'body_exact':True,'sha256':hashlib.sha256(expected.encode()).hexdigest(),'owner':owner})
    assert out['cluster']==lab['cluster'] and out['caller_state']=='aborted' and out['other_backends']==0
    assert not any(out['shared_rows'].values()) and not any(out['parent_reservations'].values())
    assert out['fact_original_exact'] and out['catalog_profile_installed'] is False
    assert all(not any(v for k,v in role.items() if k!='rolname') for role in out['roles'])
    out.update(receipt_nodes=8,real_signed_certificates=4,physical_comparison_positive=True,late_writer_rejected=True,actual_missing_end_commit_rejected=True,full_admission_commit=False,formal_root_provenance=False,whole_fixture_pass=False,execution_allowed=False,full_task_delivered=False)
    (b/'independent-readback.json').open('x').write(json.dumps(out,indent=2)+'\n')
    print(json.dumps({k:out[k] for k in ['database','caller_state','receipt_nodes','physical_comparison_positive','late_writer_rejected','actual_missing_end_commit_rejected','whole_fixture_pass']}))
