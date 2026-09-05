from datetime import datetime,timezone
from unittest.mock import MagicMock,patch

import pytest
from psycopg.pq import TransactionStatus

from aos_api.extension_runtime.release_revalidation import RuntimeReleaseRevalidator
from aos_api.asset_registry.errors import RegistrySnapshotStaleError


@pytest.mark.parametrize("case",["valid","missing","revoked"])
def test_fresh_policy_under_registry_lock(case):
    selected=MagicMock(publisher="aos",id="test",version="1.0.0",content_hash="hash",
        signature_fingerprint="fingerprint",release_evidence_revision="evidence-1")
    lock=MagicMock();lock.payload.resolved=[selected]
    conn=MagicMock();conn.info.transaction_status=TransactionStatus.INTRANS
    now=datetime.now(timezone.utc)
    conn.execute.return_value.fetchone.return_value={"checked_at":now}
    conn.execute.return_value.fetchall.return_value=[] if case=="missing" else [dict(publisher="aos",bundle_id="test",version="1.0.0")]
    policy=MagicMock(); fresh=policy.snapshot.return_value
    if case=="revoked":
        fresh.evaluate.side_effect=RegistrySnapshotStaleError("revoked")
    record=MagicMock(content_hash="hash")
    record.manifest.spec.contributions=[]
    with patch("aos_api.extension_runtime.release_revalidation.StoredCompositionLock.model_validate",return_value=lock),patch(
        "aos_api.extension_runtime.release_revalidation._record_from_row",return_value=record):
        if case=="valid":
            assert RuntimeReleaseRevalidator(release_policy=policy).revalidate_in_transaction(conn,lock=lock).checked_at==now
            fresh.evaluate.assert_called_once_with(record,checked_at=now,expected_signature_fingerprint="fingerprint",expected_evidence_revision="evidence-1")
        else:
            with pytest.raises(RegistrySnapshotStaleError):
                RuntimeReleaseRevalidator(release_policy=policy).revalidate_in_transaction(conn,lock=lock)
    assert conn.execute.call_args_list[0].args==("SELECT pg_advisory_xact_lock(228, 1)",)
    policy.snapshot.assert_called_once_with()
    policy.evaluate.assert_not_called()
