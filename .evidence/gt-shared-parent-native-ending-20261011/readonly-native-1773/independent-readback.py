"""Readonly post-test reconciliation, no Source, arm or formal DB operation."""
import hashlib,json,pathlib,subprocess
import psycopg
B=pathlib.Path(__file__).resolve().parent
R=next(p for p in B.parents if (p/'services/aos-api/postgres-extensions/aos_admission_end').is_dir())
spec=json.loads((B/'spec.json').read_text())
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
baseline=json.loads((B.parent/'mapping-identity-1771/independent-readback.json').read_text())
info=json.loads(subprocess.check_output(['docker','inspect',lab['name']]))[0]
assert info['Id']==lab['container_id'] and info['Image']==lab['image'] and info['State']['Running']
roles=['aos_physical_capacity_occupation_owner','aos_provider_capacity_issuer','aos_provider_capacity_occupation','aos_model_eval_issuer_owner','aos_capacity_publication_owner']
with psycopg.connect(host='127.0.0.1',port=lab['port'],user='aos_app',dbname=spec['database'],passfile=lab['passfile'],connect_timeout=5) as c:
    c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
    assert c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]==lab['cluster']
    for name in ('loaded_module_paths','loaded_module_file_facts','loaded_module_mapping_facts','loaded_module_readonly_facts'):
        assert c.execute('SELECT to_regprocedure(%s)',('aos_admission_native_private.'+name+'()',)).fetchone()[0] is None
    original=list(c.execute("SELECT prosrc,probin,proacl::text FROM pg_proc WHERE oid='aos_admission_native_private.pending_relations()'::regprocedure").fetchone())
    assert original==baseline['original_pending_metadata']
    for role in roles:
        flags=c.execute('SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s',(role,)).fetchone()
        assert flags is not None and not any(flags)
        assert c.execute('SELECT count(*) FROM pg_auth_members WHERE member=%s::regrole OR roleid=%s::regrole',(role,role)).fetchone()[0]==0
    c.rollback()
checks={spec['library']:spec['library_sha256'],spec['foreign_library']:spec['foreign_library_sha256'],'/usr/local/lib/postgresql/aos_ed25519.so':'6054f5dd98337b2da957ba7984333f96e26c7141b0a8d8fbd4e3981d2bc4745e'}
for path,digest in checks.items():
    assert subprocess.check_output(['docker','exec',lab['name'],'sha256sum',path],text=True).split()[0]==digest
P=R/'services/aos-api/postgres-extensions/aos_admission_end'
for name,digest in spec['source_hashes'].items():assert hashlib.sha256((P/name).read_bytes()).hexdigest()==digest
proof=json.loads((B/'module-proof.json').read_text())
assert all(proof[k] for k in ('native_readonly_bytes_independently_equal','readonly_memory_byte_change_denied','readonly_memory_exactly_restored','readonly_error_descriptors_released','rollback_only_installation_absent','original_pending_reader_exact'))
assert not proof['foreign_arm_invoked'] and proof['readonly_segment_count']>=26
out={'status':'GREEN','container_cluster_exact':True,'all_four_new_interfaces_absent':True,'original_pending_metadata_exact':True,'five_owners_flags_and_memberships_closed':True,'original_crypto_foreign_and_new_artifact_hashes_exact':checks,'native_readonly_segment_count':proof['readonly_segment_count'],'all_original_four_C_bodies_exact_prefix':(P/'aos_admission_end.c').read_bytes().startswith(subprocess.check_output(['git','show','69186f397:services/aos-api/postgres-extensions/aos_admission_end/aos_admission_end.c'])),'no_formal_database_operation':True,'execution_allowed':False,'full_task_delivered':False}
assert out['all_original_four_C_bodies_exact_prefix']
(B/'independent-readback.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k!='original_crypto_foreign_and_new_artifact_hashes_exact'}))
