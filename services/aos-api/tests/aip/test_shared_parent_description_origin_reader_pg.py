"""Owned native node callback for original description provenance only."""
import copy
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
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


def verify_native_description_origin(conn, params, command, manifest, description, policy, evidence_dir,
        *, https_signer=None):
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
    if https_signer is not None:
        # Controlled test barrier after real SQL and real typed parsing. This is
        # elapsed-time evidence, not a claimed PostgreSQL row-lock wait.
        from aos_api.oidc import verify_access_token
        from aos_api.aip_provider_capacity_source_contracts import ProviderCapacityConsumptionCommand
        sign,_=https_signer
        original_claims=verify_access_token(command.bearer_token.get_secret_value())
        expiry=int(time.time())+8
        token=sign(original_claims['sub'],changes={'exp':expiry})
        claims=verify_access_token(token)
        assert claims['exp']==expiry and claims['sub']==original_claims['sub']
        body=command.model_dump(exclude={'bearer_token'})
        body['bearer_token']=token
        short=ProviderCapacityConsumptionCommand.model_validate(body)
        actual_type=api.SharedParentRiskDescriptionPreparation
        consume=api.consume_capacity_source_for_occupation
        observations={'source_calls':[],'barrier_entered':False}
        original_source=[]
        def clock():
            row=conn.execute('SELECT clock_timestamp() AS now,pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
            return dict(now=row['now'].isoformat(),xid=row['xid'],pid=row['pid'])
        class OriginalRowBarrier:
            @staticmethod
            def model_validate(value):
                parsed=actual_type.model_validate(value)
                assert parsed==description
                observations['before']=clock()
                assert datetime.fromisoformat(observations['before']['now']).timestamp()<expiry
                observations['barrier_entered']=True
                Event().wait(max(0,expiry+.2-time.time()))
                observations['after']=clock()
                assert datetime.fromisoformat(observations['after']['now']).timestamp()>expiry
                assert (observations['before']['xid'],observations['before']['pid']) == (observations['after']['xid'],observations['after']['pid'])
                return parsed
        def actual_source(*a,**kw):
            attempt=clock();observations['source_calls'].append(attempt)
            try:
                result=consume(*a,**kw)
                attempt['succeeded']=True
                original_source.append(result)
                return result
            except Exception as exc:
                attempt['succeeded']=False;attempt['exception_class']=type(exc).__name__
                raise
        with conn.transaction(force_rollback=True):
            with pytest.MonkeyPatch.context() as patch:
                patch.setattr(api,'SharedParentRiskDescriptionPreparation',OriginalRowBarrier)
                patch.setattr(api,'consume_capacity_source_for_occupation',actual_source)
                with pytest.raises(ModelEvalOwnerRejected) as rejection:
                    api.read_shared_parent_description_origin(conn,scope,short,manifest,**args)
            assert observations['barrier_entered']
            assert len(observations['source_calls'])==2
            assert observations['source_calls'][0]['succeeded'] and not observations['source_calls'][1]['succeeded']
            assert datetime.fromisoformat(observations['source_calls'][1]['now']).timestamp()>expiry
            with pytest.raises(Exception):verify_access_token(token)
            chain=[];exc=rejection.value
            while exc is not None and len(chain)<8:
                chain.append(dict(exception_class=type(exc).__name__,sqlstate=getattr(exc,'sqlstate',None)))
                exc=exc.__context__
        assert consume(conn,command)==original_source[0]
        (Path(evidence_dir)/'post-row-auth-expiry-proof.json').open('x').write(json.dumps(dict(
            observations=observations,authentication_expires_at=datetime.fromtimestamp(expiry,timezone.utc).isoformat(),
            description_hash=description.content_hash,rejection_chain=chain,actual_original_row_parsed=True,
            original_long_authentication_still_consumes_source=True,clock_mocked=False,pg_row_lock_wait_claimed=False,
            signed_authentication_expired=True,execution_allowed=False,full_task_delivered=False),indent=2)+'\n')
        negatives.append('post_row_read_authentication_expiry')
    (Path(evidence_dir)/'native-origin-reader-proof.json').open('x').write(json.dumps(dict(
        actual_origin=dict(xid=description.immutable.caller_xid,pid=description.immutable.caller_pid),
        foreign_origin=foreign,description_hash=description.content_hash,exact_original_row=True,
        cases=len(description.immutable.manifest.cases),negative_cases=negatives,runtime_table_access=acl,
        root_provenance_verified=False,identity_same_caller_verified=False,execution_allowed=False,full_task_delivered=False),indent=2)+'\n')
