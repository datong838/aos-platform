"""Native release timestamps survive app-clock skew; no Provider execution."""
from datetime import UTC, datetime, timedelta

from aos_api import aip_release_publication_service as release_module
from aos_api.db import connect
from aos_api.aip_release_publication_models import PublishReleaseRequest, RevokePublicationRequest
from tests.extension_runtime.test_ecommerce_content_review_pending_pg import (
    SCOPE, _register_current_content_eval_gate,
)


def test_original_release_is_current_with_future_application_clock(monkeypatch):
    class ClockMeta(type):
        def __instancecheck__(cls, value):
            return isinstance(value, datetime)

    class FutureClock(datetime, metaclass=ClockMeta):
        skew = 5
        @classmethod
        def now(cls, tz=None):
            return datetime.now(tz) + timedelta(seconds=cls.skew)

    monkeypatch.setattr(release_module, "datetime", FutureClock)
    exact, _, _ = _register_current_content_eval_gate(connect)
    with connect(SCOPE) as conn:
        row = conn.execute("""SELECT g.decision_id,g.decided_at,e.occurred_at,
            clock_timestamp() AS now
            FROM aip_eval_contract_revision c
            JOIN aip_release_gate_decision g
              ON g.org_id=c.org_id AND g.project_id=c.project_id
             AND g.decision_id=c.release_gate_ref->>'resourceId'
            JOIN aip_publication_event e
              ON e.org_id=c.org_id AND e.project_id=c.project_id
             AND e.event_id=c.publication_ref->>'resourceId'
            WHERE c.org_id=%s AND c.project_id=%s
              AND c.contract_id=%s AND c.revision=%s""",
            (*SCOPE.key, exact.resource_id, exact.revision)).fetchone()
        assert row is not None
        assert row["decided_at"] <= row["occurred_at"] <= row["now"]
        assert FutureClock.now(UTC) - row["now"] > timedelta(seconds=4)
    FutureClock.skew = -5
    event = release_module.AipReleasePublicationService().publish(
        SCOPE, actor="fixture", request=PublishReleaseRequest(
            release_gate_decision_id=row["decision_id"], reason_hash="d" * 64,
            idempotency_key="clock-backward-publication"))
    with connect(SCOPE) as conn:
        now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        assert row["decided_at"] <= event.occurred_at <= now
        assert event.occurred_at - FutureClock.now(UTC) > timedelta(seconds=4)
    revoked = release_module.AipReleasePublicationService().revoke(
        SCOPE, publication_id=event.publication_id, actor="fixture",
        request=RevokePublicationRequest(reason_hash="d" * 64,
                                        idempotency_key="clock-backward-revoke"))
    assert revoked.occurred_at >= event.occurred_at
    with connect(SCOPE) as conn:
        latest = conn.execute("""SELECT event_type FROM aip_publication_event
            WHERE org_id=%s AND project_id=%s AND publication_id=%s
            ORDER BY occurred_at DESC,event_id DESC LIMIT 1""",
            (*SCOPE.key, event.publication_id)).fetchone()
        assert latest["event_type"] == "revoked"
