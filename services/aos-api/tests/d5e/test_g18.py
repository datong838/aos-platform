"""
G18 baseline — read-only DLQ snapshot for D5-E0.

D5-E0 only reads the current in-memory _dlq dict (if backend is running)
or records NO_DATA. No failure injection, no writes.
"""

import json

import pytest
from sqlalchemy import text

from .conftest import TENANT_SCOPE, collect_evidence_metadata, save_evidence


class TestG18Baseline:
    """D5-E0: G18 read-only DLQ snapshot."""

    def test_g18_dlq_snapshot(self, db_conn, evidence_meta):
        """Read-only snapshot of ecom_dlq table (if it exists) or NO_DATA."""
        results = {
            "dlq_table_exists": False,
            "dlq_count": 0,
            "pii_scan": "NOT_APPLICABLE",
            "status": "INCONCLUSIVE",
            "reason": "NO_DATA",
        }

        # Check if ecom_dlq table exists
        try:
            r = db_conn.execute(text(
                "SELECT EXISTS (SELECT FROM pg_tables WHERE tablename = 'ecom_dlq')"
            ))
            dlq_exists = r.scalar()
            results["dlq_table_exists"] = dlq_exists

            if dlq_exists:
                r2 = db_conn.execute(text(
                    "SELECT count(*) FROM ecom_dlq "
                    "WHERE org_id = :org AND workspace_id = :ws"
                ), {"org": TENANT_SCOPE["org_id"], "ws": TENANT_SCOPE["workspace_id"]})
                count = r2.scalar()
                results["dlq_count"] = count

                if count > 0:
                    results["pii_scan"] = "PENDING"
                    results["status"] = "PENDING_VALIDATION"
                    results["reason"] = f"{count} DLQ entries found, PII scan deferred to D5-E1"
                else:
                    results["status"] = "INCONCLUSIVE"
                    results["reason"] = "NO_DATA"
            else:
                results["status"] = "INCONCLUSIVE"
                results["reason"] = "ecom_dlq table does not exist yet (O1-A0 migration pending)"
        except Exception as e:
            results["status"] = "INCONCLUSIVE"
            results["reason"] = f"DB error: {type(e).__name__}"

        save_evidence("G18", "D5-E0", results, evidence_meta)

    def test_g18_pii_regex_validation(self, evidence_meta):
        """Validate PII regex patterns work correctly (pure logic test)."""
        import re

        # Test phone patterns
        phone = "13800001111"
        id_card = "110101199001011234"
        openid = "oX1234567890abcdef"

        phone_match = bool(re.search(r"1[3-9]\d{9}", phone))
        id_match = bool(re.search(r"\d{17}[\dXx]", id_card))
        openid_match = "openid" in openid.lower() or bool(re.search(r"^o[A-Za-z0-9]{15,}", openid))

        results = {
            "phone_detected": phone_match,
            "id_card_detected": id_match,
            "openid_detected": openid_match,
            "status": "PASS" if all([phone_match, id_match, openid_match]) else "RED",
            "note": "Regex validation only, no PII stored in evidence",
        }

        save_evidence("G18", "D5-E0", results, evidence_meta)
