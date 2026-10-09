"""Owned native node callback for original description provenance only."""
import copy
import json
import re
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from aos_api import aip_shared_parent_description_origin_reader as api
from aos_api.aip_model_eval_execution_owner import ModelEvalOwnerRejected
from aos_api.aip_provider_capacity_source_consumer import _consumption_packet
from aos_api.tenant_scope import TenantScope, apply_transaction_scope
from tests.aip._runtime_guard_history_fixture import isolated_owner


def test_reader_artifact_has_no_mutations_or_table_grants():
    sql='\n'.join(api.shared_description_origin_statements())
    assert not re.search(r'\b(INSERT|UPDATE|DELETE|TRUNCATE|CREATE TABLE)\b',sql)
    assert 'SET search_path=pg_catalog' in sql and 'FROM PUBLIC' in sql
    assert 'pg_current_xact_id()' in sql and 'pg_backend_pid()' in sql


def verify_native_description_origin(conn, params, command, manifest, description, policy, evidence_dir):
    scope=TenantScope('org-org','dev-project')
    args=dict(expected_content_hash=description.content_hash,**policy)
    assert api.read_shared_parent_description_origin(conn,scope,command,manifest,**args)==description
    assert api.read_shared_parent_description_origin(conn,scope,command,manifest,**args)==description
    negatives=[]
    for name,changed_scope,changed_manifest,changed_hash in (
        ('wrong_hash',scope,manifest,'sha256:'+'0'*64),
        ('hash_bool',scope,manifest,True),
        ('canary',TenantScope('dev-org','dev-project'),manifest,description.content_hash),
    ):
        with conn.transaction(force_rollback=True):
            with pytest.raises(ModelEvalOwnerRejected):
                api.read_shared_parent_description_origin(conn,changed_scope,command,changed_manifest,
                    expected_content_hash=changed_hash,**policy)
        negatives.append(name)
    changed=copy.deepcopy(manifest);changed['cases'][0]['target']['identityId']+='-drift'
    with conn.transaction(force_rollback=True):
        with pytest.raises(ModelEvalOwnerRejected):
            api.read_shared_parent_description_origin(conn,scope,command,changed,**args)
    negatives.append('complete_manifest_drift')
    packet=_consumption_packet(command);ref=Jsonb(command.source_ref.model_dump(mode='json',by_alias=True))
    sql='SELECT public.read_capacity_shared_risk_description_origin(%s,%s::jsonb,%s::uuid,%s)'
    with conn.transaction(force_rollback=True):
        with pytest.raises(psycopg.Error):conn.execute(sql,(packet,ref,uuid4(),description.content_hash))
    negatives.append('absent_native_plan')
    with psycopg.connect(**params,row_factory=dict_row) as other:
        other.isolation_level=psycopg.IsolationLevel.SERIALIZABLE
        other.execute("SET LOCAL TimeZone='UTC'");apply_transaction_scope(other,scope)
        with other.transaction(force_rollback=True):
            with pytest.raises(psycopg.Error):other.execute(sql,(packet,ref,description.plan_id,description.content_hash))
        foreign=other.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
        other.rollback()
    assert foreign['xid']!=description.immutable.caller_xid and foreign['pid']!=description.immutable.caller_pid
    negatives.append('different_actual_scram_caller')
    with isolated_owner() as admin:
        with admin.transaction(force_rollback=True):
            with pytest.raises(psycopg.Error):admin.execute(sql,(packet,ref,description.plan_id,description.content_hash))
        acl=admin.execute("SELECT has_table_privilege('aos_runtime','aos_physical_capacity_occupation_private.prepared_shared_risk_description','SELECT') AS read,has_table_privilege('aos_runtime','aos_physical_capacity_occupation_private.prepared_shared_risk_description','INSERT') AS write").fetchone()
        assert not any(acl.values())
    negatives.append('administrator_is_not_native_occupation')
    assert api.read_shared_parent_description_origin(conn,scope,command,manifest,**args)==description
    (Path(evidence_dir)/'native-origin-reader-proof.json').open('x').write(json.dumps(dict(
        actual_origin=dict(xid=description.immutable.caller_xid,pid=description.immutable.caller_pid),
        foreign_origin=foreign,description_hash=description.content_hash,exact_original_row=True,
        cases=len(description.immutable.manifest.cases),negative_cases=negatives,runtime_table_access=acl,
        root_provenance_verified=False,identity_same_caller_verified=False,execution_allowed=False,full_task_delivered=False),indent=2)+'\n')
