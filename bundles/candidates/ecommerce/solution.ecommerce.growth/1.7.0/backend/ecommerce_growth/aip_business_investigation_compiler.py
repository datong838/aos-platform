"""Deterministic N4 command identity compiler."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


def canonical_command_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


__all__ = ["canonical_command_hash"]
