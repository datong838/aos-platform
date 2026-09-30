#!/usr/bin/env python3
"""Fail closed on HBA paths that could bypass the network approval issuer password."""

from __future__ import annotations

import argparse
import ipaddress
import json
import sys


ISSUER = "aos_network_approval_issuer"


class IssuerHbaBlocked(RuntimeError):
    pass


def _contains(value: object, exact: str) -> bool:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise IssuerHbaBlocked("ISSUER_HBA_UNSAFE")
    if any(item.startswith(("+", "@")) for item in value):
        raise IssuerHbaBlocked("ISSUER_HBA_UNSAFE")
    return "all" in value or exact in value


def _matches(row: dict[str, object], *, database: str, lane: str) -> bool:
    kind = row["type"]
    if lane == "local":
        if kind != "local":
            return False
    elif kind not in ({"host", "hostssl"} if lane.endswith("ssl") else {"host", "hostnossl"}):
        return False
    if not _contains(row["database"], database) or not _contains(row["user_name"], ISSUER):
        return False
    if lane == "local":
        return True
    address = row["address"]
    if address == "all":
        return True
    if not isinstance(address, str) or not isinstance(row["netmask"], str):
        raise IssuerHbaBlocked("ISSUER_HBA_UNSAFE")
    try:
        target = ipaddress.ip_address("127.0.0.1" if lane.startswith("v4") else "::1")
        if ipaddress.ip_address(address).version != target.version:
            return False
        if lane.startswith("v6"):
            mask = int(ipaddress.IPv6Address(row["netmask"]))
            prefix = mask.bit_count()
            if mask != (((1 << prefix) - 1) << (128 - prefix)):
                raise ValueError("non-contiguous IPv6 mask")
            network = ipaddress.ip_network(f"{address}/{prefix}", strict=False)
        else:
            network = ipaddress.ip_network(f"{address}/{row['netmask']}", strict=False)
        return target in network
    except ValueError:
        raise IssuerHbaBlocked("ISSUER_HBA_UNSAFE") from None


def assess_hba_rows(rows: object, *, database: str) -> None:
    """Require an exact issuer/SCRAM first match for every local loopback lane."""
    if (not isinstance(rows, list) or not rows or not isinstance(database, str)
            or not database or any(not isinstance(row, dict) for row in rows)):
        raise IssuerHbaBlocked("ISSUER_HBA_UNSAFE")
    try:
        ordered = sorted(rows, key=lambda row: row["line_number"])
        if any(row.get("error") is not None for row in ordered):
            raise IssuerHbaBlocked("ISSUER_HBA_UNSAFE")
        for lane in ("local", "v4ssl", "v4plain", "v6ssl", "v6plain"):
            first = next((row for row in ordered if _matches(row, database=database, lane=lane)), None)
            if (first is None or first["auth_method"] != "scram-sha-256"
                    or first["database"] != [database]
                    or first["user_name"] != [ISSUER]):
                raise IssuerHbaBlocked("ISSUER_HBA_UNSAFE")
    except (KeyError, TypeError, ValueError) as exc:
        raise IssuerHbaBlocked("ISSUER_HBA_UNSAFE") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True)
    args = parser.parse_args()
    try:
        assess_hba_rows(json.load(sys.stdin), database=args.database)
    except (IssuerHbaBlocked, json.JSONDecodeError):
        print("ISSUER_HBA_UNSAFE")
        return 2
    print("ISSUER_HBA_GATE_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
