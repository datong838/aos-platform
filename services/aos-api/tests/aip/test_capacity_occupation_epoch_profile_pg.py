"""Explicit occupation epoch profile, preserving the default installation."""
import pytest
import psycopg
from psycopg.types.json import Jsonb
from uuid import uuid4

from tests.aip._runtime_guard_history_fixture import isolated_owner

pytest_plugins = ('tests.aip.test_capacity_source_publication_transaction_pg',)


@pytest.mark.parametrize('native_original_fact_reader', ['shared', 'distinct'], indirect=True)
def test_occupation_epoch_profile_requires_complete_native_audits(exact_public_source_caller):
    """A bare extra grant is drift; only the full explicit profile may pass."""
    from aos_api import aip_provider_capacity_publication_transaction as transaction
    neutral = 'public.aos_capacity_evidence_epoch_lock(text,text,text)'
    with isolated_owner() as admin:
        with admin.transaction():
            admin.execute('SET LOCAL ROLE aos_capacity_publication_owner')
            admin.execute('SELECT aos_capacity_publication_private.require_current_source_installation()')
        with pytest.raises(psycopg.Error):
            with admin.transaction():
                admin.execute('GRANT EXECUTE ON FUNCTION ' + neutral + ' TO aos_capacity_publication_owner')
                admin.execute('SET LOCAL ROLE aos_capacity_publication_owner')
                admin.execute('SELECT aos_capacity_publication_private.require_current_source_installation()')
        from aos_api.aip_provider_capacity_occupation_epoch_profile import occupation_epoch_profile_statements
        signatures = ['aos_capacity_publication_private.require_current_source_installation()',
                      'aos_capacity_publication_private.require_original_epoch_pair_boundary()',
                      'aos_capacity_publication_private.require_original_evidence_boundary()']
        original = admin.execute("SELECT oid,prosrc,proacl::text AS acl FROM pg_proc WHERE oid=ANY(SELECT to_regprocedure(s)::oid FROM unnest(%s::text[]) s) ORDER BY oid", (signatures,)).fetchall()
        try:
            with admin.transaction():
                for statement in occupation_epoch_profile_statements():
                    admin.execute(statement)
                admin.execute('SET LOCAL ROLE aos_capacity_publication_owner')
                admin.execute('SELECT aos_capacity_publication_private.require_current_source_installation()')
                faults = [
                    'GRANT EXECUTE ON FUNCTION public.aos_capacity_evidence_epoch_touch() TO aos_capacity_publication_owner',
                    'GRANT EXECUTE ON FUNCTION ' + neutral + ' TO aos_capacity_publication_owner WITH GRANT OPTION',
                    'GRANT EXECUTE ON FUNCTION ' + neutral + ' TO PUBLIC',
                    'GRANT EXECUTE ON FUNCTION ' + neutral + ' TO aos_provider_capacity_issuer',
                    'REVOKE EXECUTE ON FUNCTION ' + neutral + ' FROM aos_capacity_publication_owner',
                    'ALTER FUNCTION ' + neutral + ' SECURITY INVOKER',
                    'ALTER FUNCTION ' + neutral + ' OWNER TO aos_capacity_publication_owner',
                    "CREATE OR REPLACE FUNCTION public.aos_capacity_evidence_epoch_lock(p_org text,p_project text,p_id text) RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$ BEGIN RETURN 0; END $$",
                ]
                for fault in faults:
                    with pytest.raises(psycopg.Error) as rejected:
                        with admin.transaction():
                            admin.execute('RESET ROLE')
                            admin.execute(fault)
                            admin.execute('SET LOCAL ROLE aos_capacity_publication_owner')
                            from aos_api.aip_provider_capacity_publication_lock_boundary import require_publication_lock_boundary
                            with pytest.raises(ValueError):
                                require_publication_lock_boundary(admin)
                            admin.execute('SELECT aos_capacity_publication_private.require_current_source_installation()')
                    assert 'require_current_source_installation' in (rejected.value.diag.context or '')
                    admin.execute('SELECT aos_capacity_publication_private.require_current_source_installation()')
                raise RuntimeError('rollback explicit test profile')
        except RuntimeError as error:
            assert str(error) == 'rollback explicit test profile'
        restored = admin.execute('SELECT oid,prosrc,proacl::text AS acl FROM pg_proc WHERE oid=ANY(%s::oid[]) ORDER BY oid', ([r['oid'] for r in original],)).fetchall()
        assert restored == original
        with admin.transaction():
            admin.execute('SET LOCAL ROLE aos_capacity_publication_owner')
            admin.execute('SELECT aos_capacity_publication_private.require_current_source_installation()')
    assert 'occupation' not in transaction.source_private_installation_audit_sql()


@pytest.mark.parametrize('native_original_fact_reader', ['shared', 'distinct'], indirect=True)
def test_occupation_epoch_profile_keeps_issuer_publication_usable(exact_public_source_caller):
    """Existing issuer prepare/sign/commit must work with the profile installed."""
    from aos_api.aip_provider_capacity_occupation_epoch_profile import (
        occupation_public_source_profile_statements, legacy_public_source_restoration_statements,
    )
    from tests.aip.test_capacity_source_publication_transaction_pg import _refresh_native_facts_transaction
    issuer, packet, material, _ = exact_public_source_caller
    issuer.rollback()
    with isolated_owner() as admin:
        for statement in occupation_public_source_profile_statements():
            admin.execute(statement)
    try:
        _refresh_native_facts_transaction(issuer)
        command, _, _ = material['actual_command']()
        asset = 'occupation-compatible-issuer-' + uuid4().hex
        prepared = issuer.execute('SELECT * FROM public.prepare_capacity_source(%s,%s,%s,%s::jsonb)',
            (packet, command.idempotency_key, asset, Jsonb(material['refs'][-1]))).fetchone()
        raw = bytes(prepared['source_raw'])
        finalized = issuer.execute('SELECT * FROM public.commit_capacity_source(%s,%s,%s)',
            (command.idempotency_key, raw, material['source_key'].sign(raw))).fetchone()
        assert finalized['asset_id'] == asset and bytes(finalized['source_raw']) == raw
        issuer.commit()
    finally:
        issuer.rollback()
        with isolated_owner() as admin:
            for statement in legacy_public_source_restoration_statements():
                admin.execute(statement)


@pytest.mark.parametrize('native_original_fact_reader', ['shared', 'distinct'], indirect=True)
def test_occupation_epoch_profile_keeps_original_python_audits(exact_public_source_caller):
    """Full original Python authority checks remain required in the new layout."""
    from aos_api.aip_provider_capacity_occupation_epoch_profile import (
        occupation_public_source_profile_statements, legacy_public_source_restoration_statements,
    )
    from aos_api.aip_provider_capacity_formal_boundary import _require_read_boundary
    from aos_api.aip_provider_capacity_evidence_fence import _require_boundary
    from aos_api.aip_capacity_withdrawal_fence import require_withdrawal_fence
    from aos_api.aip_provider_capacity_source_issuer import check_native_capacity_supplier_inputs
    from tests.aip.test_capacity_source_publication_transaction_pg import _refresh_native_facts_transaction
    issuer, _, material, original = exact_public_source_caller
    command, policy, attestation = material['actual_command']()
    issuer.rollback()
    with isolated_owner() as admin:
        for statement in occupation_public_source_profile_statements():
            admin.execute(statement)
    try:
        _refresh_native_facts_transaction(issuer)
        _require_read_boundary(issuer)
        _require_boundary(issuer)
        require_withdrawal_fence(issuer)
        checked = check_native_capacity_supplier_inputs(issuer, command, policy, attestation,
            trust_roots=original[0]['provider'])
        assert checked.execution_allowed is False
    finally:
        issuer.rollback()
        with isolated_owner() as admin:
            for statement in legacy_public_source_restoration_statements():
                admin.execute(statement)


@pytest.mark.parametrize('native_original_fact_reader', ['shared', 'distinct'], indirect=True)
def test_occupation_epoch_profile_keeps_existing_consumer_usable(exact_public_source_caller, https_signer):
    """The existing issuer consumer survives the exact three-entry profile."""
    from aos_api.aip_provider_capacity_occupation_epoch_profile import (
        occupation_public_source_profile_statements, legacy_public_source_restoration_statements,
    )
    from aos_api.aip_provider_capacity_source_consumer import consume_current_capacity_source
    from aos_api.aip_provider_capacity_source_contracts import ProviderCapacityConsumptionCommand
    from aos_api.aip_provider_capacity_publication_contracts import PublishedProviderCapacitySourceV2, parse_signed_capacity_body
    from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef
    from tests.aip.test_capacity_source_publication_transaction_pg import _refresh_native_facts_transaction
    issuer, packet, material, original = exact_public_source_caller
    command, _, _ = material['actual_command']()
    asset = 'occupation-profile-consumer-' + uuid4().hex
    prepared = issuer.execute('SELECT * FROM public.prepare_capacity_source(%s,%s,%s,%s::jsonb)',
        (packet, command.idempotency_key, asset, Jsonb(material['refs'][-1]))).fetchone()
    raw = bytes(prepared['source_raw'])
    finalized = issuer.execute('SELECT * FROM public.commit_capacity_source(%s,%s,%s)',
        (command.idempotency_key, raw, material['source_key'].sign(raw))).fetchone()
    issuer.commit()
    source = parse_signed_capacity_body(raw, PublishedProviderCapacitySourceV2)
    sign, _ = https_signer
    consumption = ProviderCapacityConsumptionCommand(schema_version=1, tenant=source.tenant,
        source_ref=FormalExactRef(asset_type='ProviderCapacitySourceRevision', asset_id=asset,
            revision=1,content_hash=finalized['content_hash']), bearer_token=sign(original[0]['maker']))
    with isolated_owner() as admin:
        for statement in occupation_public_source_profile_statements(include_consumer=True):
            admin.execute(statement)
    try:
        _refresh_native_facts_transaction(issuer)
        xid = issuer.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid']
        consumed = consume_current_capacity_source(issuer, consumption)
        assert consumed.model_dump(mode='json',by_alias=True) == source.model_dump(mode='json',by_alias=True)
        assert consumed.execution_allowed is False
        assert issuer.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid'] == xid
    finally:
        issuer.rollback()
        with isolated_owner() as admin:
            for statement in legacy_public_source_restoration_statements(include_consumer=True):
                admin.execute(statement)
