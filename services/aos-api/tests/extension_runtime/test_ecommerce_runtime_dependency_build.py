"""Real runtime dependency omissions must not produce a green candidate build."""
import importlib.util
from pathlib import Path
import json
import pytest

ROOT=Path(__file__).resolve().parents[4]
s=importlib.util.spec_from_file_location('dependency_builder',ROOT/'scripts/build_ecommerce_runtime_candidates.py')
B=importlib.util.module_from_spec(s);s.loader.exec_module(B)

def bundle(tmp_path, source='from pydantic import BaseModel\n'):
    p=tmp_path/'backend/pkg';p.mkdir(parents=True);(p/'__init__.py').write_text(source)
    return tmp_path

def test_runtime_lock_records_actual_required_closure(tmp_path):
    root=bundle(tmp_path)
    deps=B._runtime_dependencies(root)
    assert {d['name'] for d in deps}=={'pydantic','pydantic-core','annotated-types','typing-extensions','typing-inspection'}
    raw=B._dependency_lock(root)
    assert raw.startswith(B.RUNTIME_LOCK)
    assert all(f"{d['name']}=={d['version']} --hash={d['hash']}\n".encode() in raw for d in deps)

def test_sdk_only_package_retains_original_lock(tmp_path):
    root=bundle(tmp_path,'from aos_extension_sdk import DispatchRef\n')
    assert B._dependency_lock(root)==B.RUNTIME_LOCK
    assert B._runtime_dependencies(root)==[]

def test_sbom_cannot_recycle_conflicting_dependency_version(tmp_path):
    root=bundle(tmp_path);(root/'evidence').mkdir();p=root/'evidence/sbom.json'
    p.write_text(json.dumps({'components':[{'type':'library','name':'pydantic','version':'0.0.0'}]}));old=p.read_bytes()
    with pytest.raises(B.CandidateBuildBlocked,match='pydantic'):
        B._augment_sbom(root,sdk_hash='a',base_config_digest='b')
    assert p.read_bytes()==old

def test_corrupt_cached_wheel_blocks_before_install_or_download(tmp_path,monkeypatch):
    root=bundle(tmp_path/'source');build=tmp_path/'build';build.mkdir();w=build/'wheelhouse';w.mkdir()
    dep=B._runtime_dependencies(root)[0];(w/dep['file']).write_bytes(b'corrupt')
    monkeypatch.setattr(B.urllib.request,'urlopen',lambda *a,**k: (_ for _ in ()).throw(AssertionError('network')))
    with pytest.raises(B.CandidateBuildBlocked,match='wheel'):
        B._stage_runtime_dependencies(root,build)
    assert not (build/'runtime-requirements.txt').exists()

def test_new_dependency_sbom_is_exact_and_repeatable(tmp_path):
    root=bundle(tmp_path);(root/'evidence').mkdir();p=root/'evidence/sbom.json';p.write_text('{"components":[]}')
    B._augment_sbom(root,sdk_hash='a',base_config_digest='b');old=p.read_bytes()
    B._augment_sbom(root,sdk_hash='a',base_config_digest='b');assert p.read_bytes()==old
    byname={v['name']:v for v in json.loads(old)['components']}
    for dep in B._runtime_dependencies(root):
        assert byname[dep['name']]['version']==dep['version']
        assert byname[dep['name']]['hashes']==[{'alg':'SHA-256','content':dep['hash'][7:]}]

@pytest.mark.parametrize('exit_code,mounts',[(1,[]),(0,[{'Type':'bind'}])])
def test_runtime_probe_never_accepts_exit_zero_with_failed_or_unisolated_image(tmp_path,monkeypatch,exit_code,mounts):
    state={'State':{'ExitCode':exit_code,'Running':False},'Mounts':mounts,
           'HostConfig':{'ReadonlyRootfs':True,'NetworkMode':'none'}}
    monkeypatch.setattr(B,'_docker',lambda context,*args,**kwargs: json.dumps([state]) if args[0]=='inspect' else 'id')
    from types import SimpleNamespace
    monkeypatch.setattr(B.subprocess,'run',lambda *args,**kwargs: SimpleNamespace(returncode=0,stdout='registration PASS',stderr=''))
    with pytest.raises(B.CandidateBuildBlocked) as exc:
        B._probe_runtime_imports(context='isolated',image_id='sha256:'+'a'*64,package='pkg',work=tmp_path)
    assert exc.value.reason_code=='RUNTIME_IMPORT_FAILED'
    assert json.loads((tmp_path/'pkg-import-probe.json').read_text())['passed'] is False


def test_build_image_index_binds_each_bundle_actual_lock(tmp_path,monkeypatch):
    import shutil
    source=tmp_path/'source';source.mkdir()
    cases=(('domain.ecommerce.core/1.4.3','domain.ecommerce.core','1.4.3','ecommerce_core'),('solution.ecommerce.growth/1.13.1','solution.ecommerce.growth','1.13.1','ecommerce_growth'))
    originals=(ROOT/'bundles/candidates/ecommerce/domain.ecommerce.core/1.4.3',ROOT/'.evidence/qyh-growth-source-candidate-20261012/candidate/solution.ecommerce.growth/1.13.1')
    for case,original in zip(cases,originals):
        root=source/case[0];shutil.copytree(original,root)
        (root/'evidence').mkdir(exist_ok=True);(root/'evidence/sbom.json').write_text('{"components":[]}')
    monkeypatch.setattr(B,'CANDIDATE_ROOT',source);monkeypatch.setattr(B,'RUNTIME_CASES',cases);monkeypatch.setattr(B,'ALL_CASES',cases)
    monkeypatch.setattr(B,'preflight',lambda:{'scope':'fixture-only'})
    monkeypatch.setattr(B,'_require_isolated_engine',lambda context:{'baseConfigDigest':'sha256:'+'b'*64})
    monkeypatch.setattr(B,'_build_image',lambda **kw:('sha256:'+'c'*64,Path(kw['package']+'.tar')))
    monkeypatch.setattr(B,'_export_registry_manifest',lambda archive,fixture,repository:{'imageDigest':'sha256:'+'d'*64,'configDigest':'sha256:'+'e'*64})
    monkeypatch.setattr(B,'_pull_exact_images',lambda **kw:kw['images'])
    output=tmp_path/'output';report=B.build(context='isolated',port=18436,output=output)
    hashes=report['dependencyLockHashes'];assert hashes['domain.ecommerce.core']!=hashes['solution.ecommerce.growth']
    for relative,bundle_id,_,_ in cases:
        root=output/relative;actual=B._sha256((root/'artifacts/python-dependencies.lock').read_bytes())
        assert hashes[bundle_id]==actual
        assert json.loads((root/'artifacts/runtime-image-index.json').read_text())['images'][0]['dependencyLockHash']==actual
