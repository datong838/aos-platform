"""Reconstruct historical JSONB byte witnesses without granting runtime action."""

from dataclasses import dataclass
import hashlib
import json
import re

from aos_api.ec_ingress_journal import _digest


_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_MAX_CANONICAL_BYTES = 65536


@dataclass(frozen=True)
class HistoricalCanonicalWitness:
    binding_json: str
    manifest_json: str


def _reconstruct_one(value: object, saved_hash: str) -> str:
    if type(value) is not dict or type(saved_hash) is not str or not _HASH.fullmatch(saved_hash):
        raise ValueError("canonical witness requires exact object and hash")
    try:
        canonical = json.dumps(value, ensure_ascii=False, sort_keys=True,
                               separators=(",", ":"), allow_nan=False)
        encoded = canonical.encode("utf-8")
    except (TypeError, UnicodeError, OverflowError, ValueError) as exc:
        raise ValueError("canonical witness cannot encode saved object") from exc
    if (len(encoded) > _MAX_CANONICAL_BYTES
            or "sha256:" + hashlib.sha256(encoded).hexdigest() != saved_hash
            or "sha256:" + _digest(value) != saved_hash):
        raise ValueError("canonical witness differs from saved hash")
    return canonical


def reconstruct_witness(binding: object, request_hash: str,
                        manifest: object, manifest_hash: str) -> HistoricalCanonicalWitness:
    """Return two exact hash-matching texts; caller must separately verify lineage."""
    return HistoricalCanonicalWitness(
        binding_json=_reconstruct_one(binding, request_hash),
        manifest_json=_reconstruct_one(manifest, manifest_hash),
    )
