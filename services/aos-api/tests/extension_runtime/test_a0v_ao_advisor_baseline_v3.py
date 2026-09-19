from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_ao_advisor_baseline_v3.py"


def test_ao_policy_v3_executor_is_exact_and_fail_closed():
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'ATTEMPT_ID = "67c2331d-b73f-4863-b881-0d67e6c55508"' in text
    assert 'expectedPolicyRevision": 2' in text
    assert 'expectedCaseVersion": 4' in text
    assert '"revision": 59' in text
    assert 'recovery.get("revision") != 19' in text
    assert "a0v-s-baseline-v2-pre-target-close-20260917" in text
    assert '"store_receipts": 1' in text
    assert '"live_links": 1168' in text
    assert '"routes": 9' in text
    assert 'binding.get("revision") != 6' in text
    assert 'binding.get("execution_epoch") != 3' in text
    assert 'current_occurrences[0]["status"] not in' in text
    assert 'no mutation was performed' in text
    assert "run_definition" not in text
    assert "sourceRowsRead" not in text
    assert "INSERT INTO" not in text
    assert "UPDATE " not in text


def test_ao_policy_v3_uses_fresh_idempotency_and_approval():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "a0v-ao-advisor-baseline-policy-put-20260919-v3" in text
    assert "a0v-ao-advisor-baseline-schedule-approval-20260919-v3" in text
    assert "AipActionStore" in text
    assert "ActionApprovalEvent" in (ROOT / "scripts/a0v_q_advisor_baseline.py").read_text(
        encoding="utf-8"
    )
    assert "EcommerceGrowthCanonicalRouter" in (
        ROOT / "scripts/a0v_q_advisor_baseline.py"
    ).read_text(encoding="utf-8")
