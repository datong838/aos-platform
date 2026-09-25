"""Reconstruct only an exact byte witness, never an ACK authorization."""

import os
from decimal import Decimal

import psycopg
from psycopg.types.json import Jsonb
import pytest

from aos_api.ec_ingress_journal import _digest
from aos_api.pipeline_snapshot_group_canonical_witness import reconstruct_witness

pytest_plugins = ("test_analysis_snapshot_resume_chain_pg",)


BINDING = {
    "schemaVersion": "aos.snapshot-group-claim/v1", "orgId": "org-org",
    "projectId": "dev-project", "groupId": "00000000-0000-4000-8000-000000000001",
    "actor": "operator", "members": [{"runId": "run-1", "draft": {"name": "中文 空格"}}],
}
MANIFEST = {"members": [{"runId": "run-1", "rowCount": 0,
                          "envelopeHash": "a" * 64, "rowsHash": "sha256:" + "b" * 64}]}


def _roundtrip(binding=BINDING, manifest=MANIFEST):
    with psycopg.connect(os.environ["AOS_DATABASE_URL"]) as conn:
        assert conn.info.dbname.startswith("aos_test_")
        return conn.execute("SELECT %s::jsonb,%s::jsonb", (Jsonb(binding), Jsonb(manifest))).fetchone()


def test_exact_historical_jsonb_roundtrip_reconstructs_witness():
    binding, manifest = _roundtrip()
    witness = reconstruct_witness(binding, "sha256:" + _digest(BINDING),
                                  manifest, "sha256:" + _digest(MANIFEST))
    assert _digest(binding) == _digest(BINDING)
    assert _digest(manifest) == _digest(MANIFEST)
    assert witness.binding_json.startswith('{"actor":"operator"')
    assert witness.manifest_json.startswith('{"members":')


@pytest.mark.parametrize("binding_hash,manifest_hash", [
    ("sha256:" + "0" * 64, "sha256:" + _digest(MANIFEST)),
    ("sha256:" + _digest(BINDING), "sha256:" + "0" * 64),
    ("sha256:" + _digest(MANIFEST), "sha256:" + _digest(BINDING)),
])
def test_hash_drift_or_cross_object_swap_rejected(binding_hash, manifest_hash):
    binding, manifest = _roundtrip()
    with pytest.raises(ValueError, match="canonical witness"):
        reconstruct_witness(binding, binding_hash, manifest, manifest_hash)


def test_non_finite_or_oversized_witness_rejected():
    with pytest.raises(ValueError, match="canonical witness"):
        reconstruct_witness({"number": float("nan")}, "sha256:" + "0" * 64,
                            MANIFEST, "sha256:" + _digest(MANIFEST))
    with pytest.raises(ValueError, match="canonical witness"):
        reconstruct_witness({"text": "x" * 70000}, "sha256:" + "0" * 64,
                            MANIFEST, "sha256:" + _digest(MANIFEST))
    with pytest.raises(ValueError, match="canonical witness"):
        reconstruct_witness({"number": Decimal("1.25")}, "sha256:" + "0" * 64,
                            MANIFEST, "sha256:" + _digest(MANIFEST))


def test_finite_decimal_shape_roundtrip_must_match_original_hash():
    original = {"number": 1.25}
    binding, manifest = _roundtrip(original)
    assert reconstruct_witness(binding, "sha256:" + _digest(original),
                               manifest, "sha256:" + _digest(MANIFEST))
    exponent = {"number": 1e20}
    binding, manifest = _roundtrip(exponent)
    with pytest.raises(ValueError, match="canonical witness"):
        reconstruct_witness(binding, "sha256:" + _digest(exponent),
                            manifest, "sha256:" + _digest(MANIFEST))


@pytest.mark.parametrize("startup_case", ["defer-host"], indirect=True)
@pytest.mark.parametrize("stored", ["qualified-runtime"], indirect=True)
def test_original_fixture_saved_group_hashes_reconstruct_without_source_call(chain_case):
    conn, state, analysis, _session, _root, _requirement = chain_case
    run_id = analysis.source.reader._journal._run_id
    rows = conn.execute("""SELECT c.binding,c.request_hash,i.manifest,i.manifest_hash
        FROM pipeline_snapshot_group_member m
        JOIN pipeline_snapshot_group_claim c USING(org_id,project_id,group_id)
        JOIN pipeline_snapshot_group_input i USING(org_id,project_id,group_id)
        WHERE m.org_id=%s AND m.project_id=%s AND m.run_id=%s""",
        (*analysis.scope.key, run_id)).fetchall()
    assert len(rows) == 1
    row = rows[0]
    witness = reconstruct_witness(row["binding"], row["request_hash"],
                                  row["manifest"], row["manifest_hash"])
    assert witness.binding_json and witness.manifest_json
    assert state["calls"] == 1
