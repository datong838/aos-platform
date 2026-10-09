"""Original committed-row faults through the exact full public issuer entry."""
from pathlib import Path
import json
from uuid import uuid4
import pytest
from psycopg.types.json import Jsonb
pytest_plugins=('tests.conftest','tests.aip.test_capacity_source_publication_transaction_pg')
B=Path(__file__).resolve().parent

@pytest.fixture(autouse=True)
def native_original_database_isolation(_isolated_postgres_database,monkeypatch):
    from tests.conftest import _isolated_postgres_database as bootstrap
    from aos_api import tenant_catalog,data_os_store
    with monkeypatch.context() as local:
        local.setattr(tenant_catalog,'_schema_ready',False)
        local.setattr(data_os_store,'_schema_ready',False)
        gen=bootstrap.__wrapped__();next(gen)
        try: yield
        finally: gen.close()

@pytest.fixture
def full_original_baseline(native_full_signed_reader):
    from tests.aip.test_capacity_source_publication_transaction_pg import _call_native_full_signed
    caller,identifier,raw,material,_=native_full_signed_reader
    original=_call_native_full_signed(caller,identifier,raw,material['refs'][-1])
    caller.rollback()
    return original['facts']

@pytest.fixture
def original_public_caller(full_original_baseline,exact_public_source_caller):
    return full_original_baseline,exact_public_source_caller

@pytest.mark.parametrize('native_original_fact_reader',['shared','distinct'],indirect=True)
@pytest.mark.parametrize('fault',['source_metadata','allocation_metadata','maker_owner','checker_owner',
    'request_hash','account_hash','basis_hash','provider_head','evidence_lifecycle','build_hash','receipt_result','allocation_status'])
def test_native_original_fact_prefix_rejects_committed_original_fact_drift(original_public_caller,native_original_fact_reader,fault,monkeypatch,request):
    from tests.aip import test_capacity_source_publication_transaction_pg as original_test
    baseline,public=original_public_caller
    caller,raw,material,_=public
    original_caller,_,args,_=native_original_fact_reader
    assert caller is original_caller
    packet=json.loads(raw)
    assert baseline['sourceProposal']==args[1]['assetId']==packet['command']['approvedProposal']['assetId']
    observations=[]
    class RollbackPrepared(Exception): pass
    def direct_public(c,identifier,current_args):
        assert c is caller and current_args==args
        identity=c.execute('SELECT session_user AS session,current_user AS role,pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
        assert identity['session']==identity['role']=='aos_provider_capacity_issuer'
        try:
            with c.transaction():
                row=c.execute('SELECT * FROM public.prepare_capacity_source(%s,%s,%s,%s::jsonb)',
                    (raw,'public-approval-'+uuid4().hex,'public-approval-source-'+uuid4().hex,Jsonb(material['refs'][-1]))).fetchone()
                assert row and bytes(row['source_raw'])
                observations.append(dict(outcome='prepared_actual_public_source',identity=identity,source_sha256=__import__('hashlib').sha256(bytes(row['source_raw'])).hexdigest()))
                raise RollbackPrepared()
        except RollbackPrepared:
            return baseline
        except Exception as error:
            observations.append(dict(outcome='native_refusal',identity=identity,type=type(error).__name__,sqlstate=getattr(error,'sqlstate',None),reason=getattr(getattr(error,'diag',None),'message_primary',None)))
            raise
        finally:
            from aos_api.db import get_dsn
            from psycopg.conninfo import conninfo_to_dict
            name=fault+'-'+request.node.callspec.params['native_original_fact_reader']+'-r2'
            (B/(name+'.json')).write_text(json.dumps(dict(fault=fault,database=conninfo_to_dict(get_dsn())['dbname'],observations=observations),indent=2))
    monkeypatch.setattr(original_test,'_call_native_original_facts',direct_public)
    original_test.test_native_original_fact_prefix_rejects_committed_original_fact_drift(native_original_fact_reader,fault)
    assert [x['outcome'] for x in observations]==['prepared_actual_public_source','native_refusal','prepared_actual_public_source']
