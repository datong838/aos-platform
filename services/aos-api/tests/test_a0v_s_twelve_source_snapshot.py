from pathlib import Path


SCRIPT = Path(__file__).parents[3] / "scripts/a0v_s_twelve_source_snapshot.py"


def test_s_snapshot_script_keeps_complete_group_and_disabled_source_schedules():
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'len(result["members"]) != 12' in text
    assert '"enabled": False, "ingest": {"kind": "pipeline-live-v1"' in text
    assert 'len(options.get("members", [])) != 12' in text
    assert 'members=members, expected_ref=None' in text
    assert 'cron="* * * * *"' in text
    assert 'intent="disable"' in text


def test_s_snapshot_script_uses_per_pipeline_keys_and_does_not_copy_old_claims():
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'f"a0v-s-snapshot-{pipeline.lower()}-selection-v1"' in text
    assert 'f"a0v-s-snapshot-{pipeline.lower()}-control-v1"' in text
    assert 'f"a0v-s-snapshot-{pipeline.lower()}-binding-v1"' in text
    assert "INSERT INTO pipeline_controlled_source_claim" not in text
    assert "INSERT INTO pipeline_snapshot" not in text


def test_consumed_product_budget_is_renewed_without_copying_claims():
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'consumed != 1' in text
    assert '"a0v-s-snapshot-p02-product-qyh-control-v2"' in text
    assert '"a0v-s-snapshot-p02-product-qyh-binding-v2"' in text
    assert 'expected_ref=disabled["ref"]' in text
    assert 'product["bindingRef"] != renewed["bindingRef"]' in text
