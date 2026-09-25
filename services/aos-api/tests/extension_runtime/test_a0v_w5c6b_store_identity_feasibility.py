"""Pure read-only Store identity classifier; no DB connection or Store apply."""

from a0v_w5c6b_store_identity_feasibility import classify


def _row():
    return dict(db='fixture', db_oid=42, server_addr='127.0.0.1',
                server_port=5432, postmaster_start='fixture-start',
                login_role='runtime-login', active_role='aos_runtime',
                fence_present=True, fence_executable=True)


def test_exact_same_physical_identity_is_candidate_not_authorization():
    result = classify(_row(), _row())
    assert result['outcome'] == 'STORE_LOCAL_FENCE_CANDIDATE_ONLY'
    assert result['storeEffectAuthorized'] is False and result['automaticAction'] is False


def test_each_missing_guard_or_identity_rejects_candidate():
    for key, value in (('db', 'other'), ('db_oid', 43), ('server_port', 5433),
                       ('postmaster_start', 'other'), ('login_role', 'other'),
                       ('active_role', 'other'), ('fence_present', False),
                       ('fence_executable', False)):
        store = _row()
        store[key] = value
        result = classify(_row(), store)
        assert result['outcome'] == 'STORE_LOCAL_FENCE_NOT_READY'
        assert result['storeEffectAuthorized'] is False


def test_incomplete_or_unknown_observation_freezes():
    assert classify({}, _row())['outcome'] == 'FROZEN_STORE_IDENTITY_AUDIT'
    assert classify(None, _row())['outcome'] == 'FROZEN_STORE_IDENTITY_AUDIT'
    unknown = _row()
    unknown['server_addr'] = None
    assert classify(_row(), unknown)['reason'] == 'PHYSICAL_IDENTITY_UNKNOWN'
