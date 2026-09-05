import base64
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from aos_api.asset_registry.canonical_json import canonical_json,canonical_sha256
from aos_api.asset_registry.composition_contracts import ResolvedBundle
from aos_api.asset_registry.contracts import BundleEvidenceType
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.extension_runtime.admission import admit_runtime_artifact


def fixture(transform_files=None, namespace="example"):
    path=Path(__file__).resolve().parents[1]/"asset_registry/test_release_policy.py"
    spec=importlib.util.spec_from_file_location("runtime_release_fixture",path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    record,roots=module._record()
    raw_manifest=record.manifest.model_dump(mode="json",by_alias=True)
    raw_manifest["spec"]["runtime"]={"apiVersion":"aos.dev/bundle-runtime/v1alpha1","backend":{
      "entrypoint":"backend/example/__init__.py:register","pythonPackage":"example","schemaNamespace":namespace,
      "profileId":"internal-python-v1","imageIndex":"artifacts/backend-image.json"}}
    record.manifest=type(record.manifest).model_validate(raw_manifest)
    import hashlib
    digest=lambda raw:"sha256:"+hashlib.sha256(raw).hexdigest()
    files={"artifacts/python-dependencies.lock":b"sdk==0.1.0\n","evidence/sbom.json":b'{"packages":[]}'}
    files["artifacts/product-query.sql"]=f"SELECT name FROM {namespace}.products WHERE id=$1".encode()
    files["artifacts/storage-registry.json"]=json.dumps({"schemaVersion":1,"queries":[{
      "operationId":"products.read","sqlPath":"artifacts/product-query.sql","table":namespace+".products",
      "columnTypes":{"id":"int8","name":"text"},"limit":100}]}).encode()
    files["artifacts/backend-image.json"]=json.dumps({"schemaVersion":1,"images":[{
      "platform":"linux/arm64","imageDigest":"sha256:"+"a"*64,"configDigest":"sha256:"+"b"*64,
      "dependencyLockHash":digest(files["artifacts/python-dependencies.lock"]),"sbomPath":"evidence/sbom.json"}]}).encode()
    if transform_files:
        transform_files(files)
    record.artifacts=[{"relativePath":path,"digest":digest(raw),"size":len(raw),"mediaType":"application/octet-stream"}
                      for path,raw in sorted(files.items())]
    descriptor={"manifest":record.manifest.model_dump(mode="json",by_alias=True,exclude_none=False),"artifacts":record.artifacts}
    record.content_hash=canonical_sha256(descriptor)
    record.signature=record.signature.model_copy(update={"signature":base64.b64encode(roots.private_key.sign(canonical_json(descriptor))).decode()})
    signature_hash=canonical_sha256(record.signature.model_dump(mode="json",by_alias=True,exclude_none=False))
    record.evidence=[item.model_copy(update={"artifact_hash":{
      BundleEvidenceType.CONTENT_HASH:record.content_hash,BundleEvidenceType.SIGNATURE_VERIFICATION:signature_hash,
      BundleEvidenceType.SBOM:digest(files["evidence/sbom.json"])}.get(item.type,item.artifact_hash)}) for item in record.evidence]
    policy=ReleasePolicy(trust_roots=roots)
    result=policy.evaluate(record,checked_at=module.NOW)
    spec=record.manifest.spec
    selected=ResolvedBundle.model_validate(dict(publisher=record.publisher,id=record.manifest.metadata.id,
      version=record.manifest.metadata.version,kind=record.manifest.kind,contentHash=record.content_hash,
      signatureFingerprint=result.signature_fingerprint,releaseEvidenceRevision=result.release_evidence_revision,
      dependencies=[],optionalDependencies=[],conflicts=[],capabilities=spec.capabilities.model_dump(mode="json",by_alias=True),permissions=spec.permissions.model_dump(mode="json",by_alias=True),
      migration={"planRef":None,"downgradePolicy":"retain-canonical"},contributions=[],selectionReason="requested"))
    class Driver:
        calls=0
        def _run(self,*args):
            self.calls+=1
            return json.dumps([{"Id":"sha256:"+"b"*64,"RepoDigests":["example@sha256:"+"a"*64],"Os":"linux","Architecture":"arm64"}])
    driver=Driver()
    return dict(record=record,selected=selected,policy=policy,checked_at=module.NOW,
                read_artifact=lambda path,limit:files[path],platform="linux/arm64",driver=driver),files


def test_signed_index_lock_sbom_and_cache_are_joined():
    args,_=fixture()
    assert admit_runtime_artifact(**args).image_id=="sha256:"+"b"*64
    assert args["driver"].calls==1


def test_query_registry_uses_exact_signed_release():
    from aos_api.extension_runtime.admission import admit_query_registry
    args,_=fixture()
    result=admit_query_registry(**{key:value for key,value in args.items() if key not in {"platform","driver"}})
    assert result[0].operation_id=="products.read"
    assert result[0].limit==100
    assert result[0].package_hash==args["record"].content_hash
    assert args["driver"].calls==0


@pytest.mark.parametrize("path",["artifacts/storage-registry.json","artifacts/product-query.sql"])
def test_query_registry_rejects_changed_bytes(path):
    from aos_api.extension_runtime.admission import admit_query_registry
    args,files=fixture()
    files[path]+=b" "
    with pytest.raises(ValueError):
        admit_query_registry(**{key:value for key,value in args.items() if key not in {"platform","driver"}})


@pytest.mark.parametrize("defect",["namespace","duplicate","unknown","limit","function","signature"])
def test_even_signed_query_definitions_must_pass_registry_contract(defect):
    from aos_api.extension_runtime.admission import admit_query_registry
    def transform(files):
        path="artifacts/storage-registry.json"
        doc=json.loads(files[path]);entry=doc["queries"][0]
        if defect=="namespace":entry["table"]="platform.products"
        if defect=="duplicate":doc["queries"].append(entry.copy())
        if defect=="unknown":entry["executeAsSuperuser"]=True
        if defect=="limit":entry["limit"]=501
        if defect=="function":files["artifacts/product-query.sql"]=b"SELECT evil($1) FROM example.products"
        files[path]=json.dumps(doc).encode()
    args,_=fixture(transform)
    if defect=="signature":args["record"].signature=None
    with pytest.raises(Exception):
        admit_query_registry(**{key:value for key,value in args.items() if key not in {"platform","driver"}})


@pytest.mark.parametrize("tamper",["signature","index","lock","sbom"])
def test_tampering_rejected_before_engine(tamper):
    args,files=fixture()
    if tamper=="signature":
        args["record"].signature=None
    else:
        path={"index":"artifacts/backend-image.json","lock":"artifacts/python-dependencies.lock","sbom":"evidence/sbom.json"}[tamper]
        files[path]+=b"x"
    with pytest.raises(Exception):
        admit_runtime_artifact(**args)
    assert args["driver"].calls==0
