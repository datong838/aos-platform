"""Reject JSONB text as the original canonical hash input."""

import json
import os

import psycopg
from psycopg.types.json import Jsonb
import pytest

from aos_api.ec_ingress_journal import _digest


@pytest.mark.parametrize("body", [
    {
        "schemaVersion": "aos.snapshot-group-claim/v1",
        "orgId": "org-org", "projectId": "dev-project",
        "groupId": "00000000-0000-4000-8000-000000000001",
        "actor": "operator", "members": [
            {"runId": "run-1", "controlRef": {"revision": 1}, "draft": {"kind": "source"}}
        ],
    },
    {"members": [{"runId": "run-1", "envelopeHash": "a" * 64,
                  "rowsHash": "sha256:" + "b" * 64, "rowCount": 0}]},
    {"members": [{"runId": "中文 空格", "nested": {"z": -1.25, "a": "a  b"}}]},
])
def test_jsonb_text_is_not_python_canonical_group_hash_input(body):
    canonical_text = json.dumps(
        body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    with psycopg.connect(os.environ["AOS_DATABASE_URL"]) as conn:
        assert conn.info.dbname.startswith("aos_test_")
        jsonb_hash, witness_hash, witness_matches = conn.execute(
            "SELECT encode(sha256(convert_to(%s::jsonb::text,'UTF8')),'hex'),"
            "encode(sha256(convert_to(%s,'UTF8')),'hex'),"
            "%s::jsonb=%s::jsonb",
            (Jsonb(body), canonical_text, canonical_text, Jsonb(body)),
        ).fetchone()
    assert jsonb_hash != _digest(body)
    assert witness_hash == _digest(body)
    assert witness_matches is True
