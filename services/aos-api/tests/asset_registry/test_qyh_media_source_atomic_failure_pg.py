"""Native rollback proof with signed fixture sources; no enterprise rollout."""
import pytest
import psycopg
from psycopg import sql

from tests.asset_registry.test_qyh_installation_source_pg import installed  # noqa: F401
from tests.asset_registry.test_qyh_complete_media_source_pg import complete_case, SCOPE  # noqa: F401


@pytest.mark.parametrize("phase", ["profile", "receipt"])
def test_original_registration_rolls_back_and_safe_retry_is_exact(complete_case, phase):
    store, factory, reader, body, admin, _ = complete_case
    key = "atomic-retry-" + phase
    with factory(SCOPE) as conn:
        assert reader(conn, SCOPE, body) is True

    counts = """SELECT
      (SELECT count(*) FROM public.aip_media_gate_profile_revision
        WHERE org_id=%s AND project_id=%s AND profile_id=%s) AS profiles,
      (SELECT count(*) FROM public.aip_production_contract_receipt
        WHERE org_id=%s AND project_id=%s AND operation='media_gate_profile.register'
        AND idempotency_key=%s) AS receipts"""
    parameters = (*SCOPE.key, body.profile_id, *SCOPE.key, key)
    assert admin.execute(counts, parameters).fetchone() == {"profiles": 0, "receipts": 0}
    table = "aip_media_gate_profile_revision" if phase == "profile" else "aip_production_contract_receipt"
    message = "QYH_FIXTURE_PROFILE_REJECT" if phase == "profile" else "QYH_FIXTURE_AFTER_PROFILE_INSERT"
    # In the late failure, a successful profile INSERT must already be visible
    # to this same database transaction. Otherwise the expected error differs.
    check_profile = ""
    if phase == "receipt":
        check_profile = """IF NOT EXISTS(SELECT 1 FROM public.aip_media_gate_profile_revision
          WHERE org_id=NEW.org_id AND project_id=NEW.project_id
            AND profile_id=NEW.result_ref->>'resourceId')
          THEN RAISE EXCEPTION 'profile was not inserted before receipt'; END IF;"""
    function = sql.SQL("""CREATE FUNCTION public.qyh_fixture_atomic_reject() RETURNS trigger
      LANGUAGE plpgsql AS $$ BEGIN {} RAISE EXCEPTION {} USING ERRCODE='23514'; END $$""").format(
        sql.SQL(check_profile), sql.Literal(message),
    )
    admin.execute(function)
    condition = sql.SQL("WHEN (NEW.operation='media_gate_profile.register')") if phase == "receipt" else sql.SQL("")
    admin.execute(sql.SQL("CREATE TRIGGER qyh_fixture_atomic_reject BEFORE INSERT ON public.{} FOR EACH ROW {} EXECUTE FUNCTION public.qyh_fixture_atomic_reject()").format(sql.Identifier(table), condition))
    try:
        with pytest.raises(psycopg.errors.CheckViolation) as failure:
            store.register_media_gate_profile(SCOPE, "fixture-source-maker", key, body)
        assert failure.value.diag.message_primary == message
        # Independent autocommit session observes no partially committed row.
        assert admin.execute(counts, parameters).fetchone() == {"profiles": 0, "receipts": 0}
    finally:
        admin.execute(sql.SQL("DROP TRIGGER qyh_fixture_atomic_reject ON public.{}").format(sql.Identifier(table)))
        admin.execute("DROP FUNCTION public.qyh_fixture_atomic_reject()")

    # Only after explicit rejection and independent rollback readback is retry
    # authorized. This is not a retry following an unknown external outcome.
    result = store.register_media_gate_profile(SCOPE, "fixture-source-maker", key, body)
    replay = store.register_media_gate_profile(SCOPE, "fixture-source-maker", key, body)
    assert result == replay
    assert result.profile_id == body.profile_id
    assert admin.execute(counts, parameters).fetchone() == {"profiles": 1, "receipts": 1}
