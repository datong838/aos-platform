"""Read the retained risk attempt only; never replay its transaction."""
import base64, hashlib, json, re
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from aos_api import aip_shared_parent_atomic_admission as api
from aos_api.aip_model_runtime_store import canonical_hash

B = Path(__file__).resolve().parent
R = B.parents[2]
result = json.loads((B / 'result-r2.json').read_text())
proof = json.loads((B / 'parent-risk-stage-proof.json').read_text())
restore = json.loads((B / 'profiler-restoration.json').read_text())
assert restore['exact_restored'] and restore['before_acl'] == restore['after_acl'] == []
assert len(result['databases']) == 1 and result['old_files_unchanged']
risk = proof['risk']
assert risk['contentHash'] == 'sha256:' + canonical_hash(risk['immutable'])
assert risk['immutable']['originalRisk'] == proof['original_origin']['immutable']['originalRisk']
assert risk['immutable']['originalRiskHash'] == 'sha256:' + canonical_hash(risk['immutable']['originalRisk'])
assert risk['immutable']['authorityMaterialHash'] == proof['retained_authority']['contentHash']
assert risk['immutable']['pendingOriginHash'] == proof['pending']['contentHash']
assert len(risk['immutable']['originalRisk']['legs']) == 4
assert len(risk['immutable']['originalRisk']['parentRisks']) == 2
assert risk['immutable']['executionAllowed'] is False
assert risk['immutable']['windowExpiryReleasesRisk'] is False
assert proof['negative_cases'] == []
assert proof['negative_cases_separately_verified'] == ['parent-risk-native-1739-r2/independent-readback.json', 'certificate-phase-native-1741-r1/independent-readback.json']
for ref in proof['negative_cases_separately_verified']:
    prior = json.loads((B.parent / ref).read_text())
    assert prior['native_caller_aborted'] and prior['negative_cases'] == ['immutable_update', 'immutable_delete', 'wrong_pending_hash', 'real_legacy_pair_requires_cutover']
component = B / 'component-native-proof.json'
actual_commit_rejected = component.exists()
if actual_commit_rejected:
    whole = json.loads(component.read_text())
    cp = whole['certificate_proof']
    assert whole['actual_commit_rejected'] and cp['live_overload_rejected']
    assert cp['live_physical_facts']['facts']['unresolvedRequests'] == 2
    assert cp['live_physical_facts']['facts']['unresolvedTokenUpperBound'] == 20000
    assert cp['actual_union_after_late_writer'] == {'requests': 3, 'tokens': 30000}
    assert whole['rollback_xid'] == proof['caller']['xid']
key = Ed25519PublicKey.from_public_bytes(base64.b64decode(proof['root']['publicKeyBase64']))
for envelope in proof['certificates']:
    message = json.dumps(envelope['certificate'], ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    key.verify(base64.b64decode(envelope['signatureBase64']), b'AOS-MODEL-EVAL-SHARED-PARENT-CERTIFICATE-SIGNING-INPUT-v3\n' + message)
assert len(proof['certificates']) == 4
lab = json.loads((R / '.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
metadata, counts = [], {}
with psycopg.connect(host='127.0.0.1', port=lab['port'], user='aos_app', dbname=result['databases'][0], passfile=lab['passfile'], row_factory=dict_row) as c:
    c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
    assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id'] == lab['cluster']
    assert c.execute('SELECT pg_xact_status(%s::xid8) AS state', (proof['caller']['xid'],)).fetchone()['state'] == 'aborted'
    for statement in api.shared_parent_complete_parent_risk_statements():
        match = re.search(r'CREATE FUNCTION ([^(]+)\(.*?\$(risk_binding|risk_stage)\$(.*?)\$\2\$', statement, re.S)
        if not match:
            continue
        name, tag, body = match.groups()
        row = c.execute('SELECT prosrc,pg_get_userbyid(proowner) AS owner,proconfig,prosecdef FROM pg_proc WHERE pronamespace=(SELECT oid FROM pg_namespace WHERE nspname=%s) AND proname=%s', tuple(name.split('.'))).fetchone()
        assert row['prosrc'] == body and row['owner'] == api.OWNER and row['proconfig'] == ['search_path=pg_catalog'] and row['prosecdef'] == (tag == 'risk_stage')
        metadata.append(dict(name=name, body_sha256=hashlib.sha256(body.encode()).hexdigest(), native_body_exact=True))
    sql = next(s for s in api.shared_parent_admission_certificate_set_statements() if s.startswith('CREATE FUNCTION '))
    body = re.search(r'\$set\$(.*?)\$set\$', sql, re.S).group(1)
    row = c.execute('SELECT prosrc,pg_get_userbyid(proowner) AS owner,proconfig,prosecdef FROM pg_proc WHERE oid=%s::regprocedure', (api.CERTIFICATE_SET,)).fetchone()
    assert row['prosrc'] == body and row['owner'] == api._certificate.ISSUER_OWNER and row['proconfig'] == ['search_path=pg_catalog'] and row['prosecdef']
    assert body.count(api._certificate.shared_parent_certificate_claim_sql()) == 1
    metadata.append(dict(name=api.CERTIFICATE_SET, body_sha256=hashlib.sha256(body.encode()).hexdigest(), native_body_exact=True))
    for signature, generator, tag in [(api.FINAL_CALL,api.shared_parent_final_call_validation_statements,'call_read'),(api.FINAL_INTENT,api.shared_parent_final_intent_validation_statements,'intents')]:
        sql=generator()[0]
        # Use the actual generated dollar tag; metadata is compared byte-exact.
        body=re.search(r'AS \$(\w+)\$(.*?)\$\1\$',sql,re.S).group(2)
        row=c.execute('SELECT prosrc,pg_get_userbyid(proowner) AS owner,proconfig,prosecdef FROM pg_proc WHERE oid=%s::regprocedure',(signature,)).fetchone()
        assert row['prosrc']==body and row['owner']==api.OWNER and row['proconfig']==['search_path=pg_catalog'] and row['prosecdef']
        for role in ('aos_runtime','aos_provider_capacity_issuer'):
            assert not c.execute("SELECT has_function_privilege(%s,%s,'EXECUTE') AS allowed",(role,signature)).fetchone()['allowed']
        assert not c.execute("SELECT EXISTS(SELECT 1 FROM pg_proc p,LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a WHERE p.oid=%s::regprocedure AND a.grantee=0 AND a.privilege_type='EXECUTE') AS allowed",(signature,)).fetchone()['allowed']
        metadata.append(dict(name=signature,body_sha256=hashlib.sha256(body.encode()).hexdigest(),native_body_exact=True))
    for role in ('aos_runtime', 'aos_provider_capacity_issuer', 'aos_model_eval_issuer_owner'):
        assert not c.execute("SELECT has_function_privilege(%s,%s,'EXECUTE') AS allowed", (role, api.STAGE_PARENT_RISK)).fetchone()['allowed']
        for privilege in ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE'):
            assert not c.execute('SELECT has_table_privilege(%s,%s,%s) AS allowed', (role, api.PHYSICAL_SCHEMA + '.complete_parent_risk', privilege)).fetchone()['allowed']
    for row in c.execute("SELECT n.nspname,c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname LIKE 'aos_shared_parent%' AND c.relkind='r'").fetchall():
        name = row['nspname'] + '.' + row['relname']
        counts[name] = c.execute('SELECT count(*) AS n FROM ' + name).fetchone()['n']
        assert counts[name] == 0
    table = api.PHYSICAL_SCHEMA + '.complete_parent_risk'
    row = c.execute('SELECT relrowsecurity,relforcerowsecurity,pg_get_userbyid(relowner) AS owner FROM pg_class WHERE oid=%s::regclass', (table,)).fetchone()
    assert row == dict(relrowsecurity=True, relforcerowsecurity=True, owner=api.OWNER)
    trigger = c.execute("SELECT tgdeferrable,tginitdeferred FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname='require_complete_risk_end'", (table,)).fetchone()
    assert trigger == dict(tgdeferrable=True, tginitdeferred=True)
    constraints = c.execute("SELECT pg_get_constraintdef(oid) AS definition FROM pg_constraint WHERE conrelid=%s::regclass AND contype='u'", (table,)).fetchall()
    assert constraints == [dict(definition='UNIQUE (org_id, project_id, target_request, judge_request)')]
    facts = risk['immutable']['originalRisk']['originalFacts']
    for purpose, table in [('target', 'aip_model_eval_budget_reservation'), ('judge', 'aip_model_judge_budget_reservation')]:
        assert c.execute('SELECT count(*) AS n FROM ' + table + ' WHERE reservation_id=%s', (facts[purpose]['reservationId'],)).fetchone()['n'] == 0
    flags = c.execute("SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname='aos_provider_capacity_occupation'").fetchone()
    assert not any(flags.values())
    assert c.execute("SELECT count(*) AS n FROM pg_auth_members WHERE member='aos_provider_capacity_occupation'::regrole OR roleid='aos_provider_capacity_occupation'::regrole").fetchone()['n'] == 0
    assert c.execute("SELECT parname FROM pg_parameter_acl WHERE parname='track_functions'").fetchall() == []
positive_path=B/'final-call-positive-proof.json'
positive=json.loads(positive_path.read_text()) if positive_path.exists() else None
if positive:
    assert positive['caller']==proof['caller']
    assert positive['before_intent_write_counts']==positive['after_intent_write_counts']
    assert positive['real_signed_original_source'] and positive['real_independent_parents']
    assert positive['signed_certificate_legs']==4 and positive['judge_actual_result_pending']
    assert positive['caller_input_bytes_match'] and not positive['execution_allowed']
output = dict(status='FIXED_FINAL_CALL_NATIVE_POSITIVE_VERIFIED' if positive else 'FIXED_FINAL_CALL_POSITIVE_NOT_REACHED', authority='AOS-001756', final_call_native_positive=bool(positive), database=result['databases'][0], cluster=lab['cluster'], native_functions=metadata, zero_rows=counts, signed_legs=4, parent_risks=2, native_caller_aborted=True, negative_cases=proof['negative_cases'], temporary_permissions_restored=True, actual_missing_end_commit_rejected=actual_commit_rejected, separate_risk_negatives=True, whole_fixture_pass=result['pytest_exit'] == 0, full_admission_commit=False, formal_root_provenance=False, execution_allowed=False, full_task_delivered=False)
(B / 'independent-readback.json').open('x').write(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: output[k] for k in ('status', 'database', 'whole_fixture_pass', 'native_caller_aborted')}))
