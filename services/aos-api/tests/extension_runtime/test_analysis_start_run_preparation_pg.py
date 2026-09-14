"""Shared Host Run creation on isolated PG; original source remains named fixture."""
from datetime import timedelta
import pytest
from test_analysis_startup_evidence_pg import (
    analysis_case,consumer_case,host_case,control_governed,governed,service_case,stored,body,pair,
)
from test_product_event_analysis_port import command
from aos_api.ecommerce_growth_runtime_adapters import AnalysisAdvanceHostService
from aos_api.ecommerce_growth_host_ports import HostTransaction


def test_original_host_run_preparation_replays_with_original_time(analysis_case):
    conn,analysis,claimed=analysis_case
    request=analysis._phase(conn,claimed,lambda _s,request,_d:request)
    start=command(request)
    service=AnalysisAdvanceHostService()
    now=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
    first=service._prepare_start_run(transaction=HostTransaction(conn),scope=analysis.scope,command=start,occurred_at=now)
    again=service._prepare_start_run(transaction=HostTransaction(conn),scope=analysis.scope,command=start,occurred_at=now+timedelta(seconds=10))
    assert first==again and first.authority.created_at==now
    assert first.authority.trigger_key==claimed.target_idempotency_key
    assert first.authority.created_by==service.executor_identity
    assert conn.execute('SELECT count(*) AS n FROM aip_task_run WHERE org_id=%s AND project_id=%s',analysis.scope.key).fetchone()['n']==0


def test_original_host_run_preparation_rolls_back(analysis_case):
    from aos_api.ecommerce_business_investigation_run import BusinessInvestigationRunStore,BusinessInvestigationRunNotFound
    from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
    conn,analysis,claimed=analysis_case
    request=analysis._phase(conn,claimed,lambda _s,request,_d:request)
    with pytest.raises(RuntimeError,match='after original run'),conn.transaction():
        first=AnalysisAdvanceHostService()._prepare_start_run(transaction=HostTransaction(conn),scope=analysis.scope,
            command=command(request),occurred_at=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now'])
        raise RuntimeError('after original run')
    with pytest.raises(BusinessInvestigationRunNotFound):
        BusinessInvestigationRunStore(TransactionBoundConnectFactory(HostTransaction(conn),analysis.scope)).get_verified(analysis.scope,first.authority.run_id)
