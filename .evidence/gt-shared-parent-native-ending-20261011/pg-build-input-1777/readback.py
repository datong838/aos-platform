"""Independently recheck installed header bytes and explicit source gaps."""
import hashlib,io,json,pathlib,subprocess,tarfile
B=pathlib.Path(__file__).resolve().parent
prior=json.loads((B/'source-header-comparison.json').read_text())
binding=json.loads((B/'archive-header-bindings.json').read_text())
raw=subprocess.check_output(['docker','cp','aos-source-desktop-shm-20261009:/usr/local/include/postgresql/server','-'],timeout=30)
assert len(raw)<32*1024*1024
observed={}
with tarfile.open(fileobj=io.BytesIO(raw),mode='r:') as t:
    for m in t.getmembers():
        if m.isdir():continue
        assert m.isfile() and m.name.startswith('server/') and m.size<4*1024*1024
        n=m.name[len('server/'):];assert '..' not in pathlib.PurePosixPath(n).parts
        observed[n]=hashlib.sha256(t.extractfile(m).read()).hexdigest()
assert observed=={n:v['installed_sha256'] for n,v in prior['files'].items()}
assert prior['counts']=={'source_equal':762,'source_differs':1,'generated_or_other_missing_archive':97}
assert binding['equal_bytes_elsewhere_archive']==94
assert binding['unbound']==['pg_config.h','pg_config_ext.h','utils/probes.h']
assert binding['socket_patch_present_in_image_history']
diff=json.loads((B/'manual-header-diff.json').read_text())['diff']
assert '#define DEFAULT_PGSOCKET_DIR  "/tmp"' in diff and '#define DEFAULT_PGSOCKET_DIR "/var/run/postgresql"' in diff
out={'status':'SCOPED_PG_SOURCE_HEADER_BINDINGS_VERIFIED','installed_headers_independently_read_back':len(observed),'archive_equal_total':856,'one_socket_directory_patch':True,'three_generated_headers_unproved':binding['unbound'],'original_binary_or_signed_build_provenance_proved':False,'no_container_or_database_mutation':True,'model_review_invoked':False,'full_task_delivered':False}
(B/'review.json').open('x').write(json.dumps(out,indent=2)+'\n')
print(json.dumps(out))
