"""Immutable staged configuration. Never mutates bindings or grants execution."""
import json
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from aos_api.asset_registry.control_policy import validate_idempotency_key
from .configuration_contracts import ConfigurationDocument, ConfigurationRef
from .lifecycle_store import _require_transaction, _values, _digest, RuntimeConflict, RuntimeRevisionConflict
from .runtime_gate import _reject_deferred


def _target(conn, org_id, project_id, installation_id, generation):
    _require_transaction(conn)
    row=conn.execute("SELECT current_setting('aos.org_id',true) AS org_id,current_setting('aos.project_id',true) AS project_id").fetchone()
    if not org_id or not project_id or _values(row,('org_id','project_id')) != (org_id,project_id):
        raise PermissionError('configuration tenant scope mismatch')
    return org_id,project_id,UUID(str(installation_id)),UUID(str(generation))


def _authorize(conn, target, actor, configuration, authorize):
    if type(actor) is not str or not 1 <= len(actor) <= 240 or not actor.isprintable() or actor != actor.strip():
        raise ValueError('exact configuration actor required')
    if not callable(authorize): raise PermissionError('current configuration authority reader required')
    result=authorize(conn,org_id=target[0],project_id=target[1],installation_id=str(target[2]),
                     generation=str(target[3]),actor=actor,configuration=configuration)
    _reject_deferred(result)
    if result is not True: raise PermissionError('current configuration references or permission unavailable')


def _content_hash(target, identity, revision, previous_hash, actor, payload):
    return _digest(dict(orgId=target[0],projectId=target[1],installationId=str(target[2]),generation=str(target[3]),
        configurationId=str(identity),revision=revision,previousHash=previous_hash,actor=actor,configuration=payload))


_COLUMNS='configuration_id,revision,payload,content_hash,previous_hash,actor'


def _decode(target, row):
    identity, revision, payload, digest, previous, actor = _values(row,tuple(_COLUMNS.split(',')))
    # JSON validation preserves strict tuples and recursively revalidates refs.
    document=ConfigurationDocument.model_validate_json(json.dumps(payload,allow_nan=False))
    if _content_hash(target,identity,revision,previous,actor,document.model_dump(mode='json')) != digest:
        raise RuntimeConflict('configuration content hash differs')
    return ConfigurationRef(configurationId=str(identity),revision=revision,hash=digest), document


def append_configuration(conn, *, org_id, project_id, installation_id, generation,
                         expected_installation_etag, expected_binding_revision, actor,
                         idempotency_key, configuration, authorize, previous_ref=None):
    target=_target(conn,org_id,project_id,installation_id,generation)
    if any(type(value) is not int or not 1<=value<2**63 for value in (expected_installation_etag,expected_binding_revision)):
        raise ValueError('positive configuration target versions required')
    idempotency_key=validate_idempotency_key(idempotency_key)
    configuration=ConfigurationDocument.model_validate(configuration)
    previous=ConfigurationRef.model_validate(previous_ref) if previous_ref is not None else None
    head=conn.execute('''SELECT etag_version FROM bundle_installation
        WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR UPDATE''',target[:3]).fetchone()
    if head is None: raise LookupError('configuration installation not found')
    binding=conn.execute('''SELECT revision,desired_state,observed_state FROM extension_runtime_binding
        WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s FOR UPDATE''',target).fetchone()
    if binding is None: raise LookupError('configuration binding not found')
    _authorize(conn,target,actor,configuration,authorize)
    payload=configuration.model_dump(mode='json')
    request_hash=_digest(dict(actor=actor,installationEtag=expected_installation_etag,bindingRevision=expected_binding_revision,
        configuration=payload,previousRef=previous.model_dump(mode='json') if previous else None))
    existing=conn.execute(f'''SELECT {_COLUMNS},request_hash FROM extension_runtime_configuration
        WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s AND idempotency_key=%s''',
        (*target,idempotency_key)).fetchone()
    if existing is not None:
        values=_values(existing,(*_COLUMNS.split(','),'request_hash'))
        if values[-1] != request_hash: raise RuntimeConflict('configuration idempotency key has another request')
        return _decode(target,values[:-1])[0]
    revision, desired, observed = _values(binding,('revision','desired_state','observed_state'))
    if _values(head,('etag_version',))[0] != expected_installation_etag or revision != expected_binding_revision:
        raise RuntimeRevisionConflict('configuration target version changed')
    if desired == 'uninstalled' or observed in {'unknown','stopped'}:
        raise RuntimeConflict('configuration target is not installed')
    if previous:
        latest=conn.execute(f'''SELECT {_COLUMNS} FROM extension_runtime_configuration
            WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s AND configuration_id=%s
            ORDER BY revision DESC LIMIT 1''',(*target,UUID(previous.configurationId))).fetchone()
        if latest is None or _decode(target,latest)[0] != previous:
            raise RuntimeRevisionConflict('configuration previous revision changed')
        identity=UUID(previous.configurationId)
        version=previous.revision+1
    else:
        identity=uuid4()
        version=1
    previous_hash=previous.hash if previous else None
    digest=_content_hash(target,identity,version,previous_hash,actor,payload)
    result=ConfigurationRef(configurationId=str(identity),revision=version,hash=digest)
    conn.execute('''INSERT INTO extension_runtime_configuration
        (org_id,project_id,installation_id,generation,configuration_id,revision,payload,content_hash,
         previous_hash,request_hash,idempotency_key,actor) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
        (*target,identity,version,Jsonb(payload),digest,previous_hash,request_hash,idempotency_key,actor))
    return result


def read_configuration(conn, *, org_id, project_id, installation_id, generation, actor, ref, authorize):
    target=_target(conn,org_id,project_id,installation_id,generation)
    ref=ConfigurationRef.model_validate(ref)
    row=conn.execute(f'''SELECT {_COLUMNS} FROM extension_runtime_configuration
        WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
        AND configuration_id=%s AND revision=%s''',(*target,UUID(ref.configurationId),ref.revision)).fetchone()
    if row is None: raise LookupError('configuration revision not found')
    actual, document=_decode(target,row)
    if actual != ref: raise RuntimeConflict('configuration reference differs')
    _authorize(conn,target,actor,document,authorize)
    return document
