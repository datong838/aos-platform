"""Signed cached schema requirements; reads only, not migration or enable authority."""
import hashlib
import json

from aos_api.asset_registry.composition_contracts import ResolvedBundle
from aos_api.asset_registry.canonical_json import canonical_sha256
from .ipc import _pairs
from .lifecycle_store import _require_transaction, _values
from .schema_registry import SchemaRequirement, require_installed


def schema_package_id(publisher, bundle_id):
    return 'bundle-'+canonical_sha256({'publisher':publisher,'id':bundle_id}).removeprefix('sha256:')


def admit_schema_requirements(*,record,selected,policy,checked_at,read_artifact):
    selected=ResolvedBundle.model_validate(selected)
    if (record.publisher,record.manifest.metadata.id,record.manifest.metadata.version,record.content_hash)!=(
            selected.publisher,selected.id,selected.version,selected.content_hash):
        raise ValueError('schema release differs from lock')
    policy.evaluate(record,checked_at=checked_at,
        expected_signature_fingerprint=selected.signature_fingerprint,
        expected_evidence_revision=selected.release_evidence_revision)
    runtime=record.manifest.spec.runtime
    if runtime is None:return ()
    if runtime.backend is None:raise ValueError('schema reader requires backend runtime')
    path='artifacts/schema-requirements.json'
    items=[item for item in record.artifacts if item['relativePath']==path]
    if len(items)!=1:raise ValueError('signed schema requirements missing')
    item=items[0]
    if type(item['size']) is not int or not 0<item['size']<=65536:
        raise ValueError('schema requirements size invalid')
    raw=read_artifact(path,65536)
    if (type(raw) is not bytes or len(raw)!=item['size']
            or 'sha256:'+hashlib.sha256(raw).hexdigest()!=item['digest']):
        raise ValueError('schema artifact differs from signed release')
    document=json.loads(raw,object_pairs_hook=_pairs)
    if (type(document) is not dict or set(document)!={'schemaVersion','requirements'}
            or type(document['schemaVersion']) is not int or document['schemaVersion']!=1
            or type(document['requirements']) is not list or len(document['requirements'])>64):
        raise ValueError('schema requirements contract invalid')
    if not document['requirements'] and (
            any(i['relativePath']=='artifacts/storage-registry.json' for i in record.artifacts)
            or record.manifest.spec.migrations.plan is not None or record.manifest.spec.exports.schemas):
        raise ValueError('storage runtime cannot omit schema requirements')
    requirements=[]
    seen=set()
    for entry in document['requirements']:
        if type(entry) is not dict or set(entry)!={'version','migrationHash'}:
            raise ValueError('invalid schema requirement')
        requirement=SchemaRequirement(schema_package_id(selected.publisher,selected.id),entry['version'],entry['migrationHash'])
        if requirement.schema_version in seen:raise ValueError('duplicate schema version')
        seen.add(requirement.schema_version)
        requirements.append(requirement)
    return tuple(requirements)


class CurrentSchemaConditions:
    """Host injects bounded local cache readers, never request-provided grants."""
    def __init__(self, *, load_record, read_artifact, policy):
        self.load_record=load_record
        self.read_artifact=read_artifact
        self.policy=policy

    def __call__(self, *,conn,locked,lock,actor):
        _require_transaction(conn)
        if not 1<=len(lock.payload.resolved)<=64:
            raise ValueError('bounded resolved schema set required')
        checked_at=_values(conn.execute('SELECT clock_timestamp() AS now').fetchone(),('now',))[0]
        for selected in lock.payload.resolved:
            record=self.load_record(selected)
            requirements=admit_schema_requirements(record=record,selected=selected,
                policy=self.policy,checked_at=checked_at,
                read_artifact=lambda path,limit:self.read_artifact(selected,path,limit))
            if requirements:require_installed(conn,requirements)
        return True
