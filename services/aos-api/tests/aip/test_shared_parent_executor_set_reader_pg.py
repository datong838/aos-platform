"""Native v3 metadata bridge regression contract; installation remains isolated."""
import re
from aos_api import aip_shared_parent_executor_set_reader as api


def test_native_v3_bridge_does_not_reuse_legacy_or_grant_tables():
    statements = api.shared_parent_executor_set_statements()
    assert len(statements) == 4
    sql = statements[0]
    assert 'SECURITY DEFINER SET search_path=pg_catalog' in sql
    assert "session_user<>'aos_provider_capacity_occupation'" in sql
    for guard in ("'aos_runtime'", "'serializable'", "'UTC'", "'origin'", "'org-org'", "'dev-project'"):
        assert guard in sql
    assert 'shared_parent_certificate_identity_binding' in sql
    assert re.search(r'(?<!shared_parent_)certificate_identity_binding', sql) is None
    for column in ('description_hash', 'original_risk_hash', 'caller_xid', 'caller_pid'):
        assert column in sql
    assert 'pg_current_xact_id()' in sql and 'pg_backend_pid()' in sql
    assert sql.index('issuer_epoch') < sql.index('certificate_epoch') < sql.index('identity_epoch')
    assert 'FOR SHARE' in sql
    assert 'executionAllowed' in sql and 'false' in sql
    assert not re.search(r'\b(INSERT|UPDATE|DELETE|TRUNCATE|COMMIT)\b', sql, re.I)
    grants = '\n'.join(statements[1:])
    assert 'FROM PUBLIC' in grants and 'GRANT EXECUTE ON FUNCTION' in grants
    assert not re.search(r'GRANT\s+(SELECT|INSERT|UPDATE|DELETE|ALL)', grants, re.I)
