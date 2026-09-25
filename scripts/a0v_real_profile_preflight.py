"""Read-only, secret-free STOP gate before any real A0-V profile start."""

import argparse
import json
from pathlib import Path
import plistlib
import subprocess


_LABEL = "com.aos.a0v-api-8080"
_PROFILE = "aos-extension"


def evaluate(plist_bytes: bytes, *, launchd_listing: str, port_8080_open: bool,
             port_18181_open: bool, profile_listing: str,
             container_policy_proven: bool = False) -> dict:
    """Only allowlisted booleans leave this function; no plist values are returned."""
    try:
        config = plistlib.loads(plist_bytes)
    except (ValueError, TypeError, plistlib.InvalidFileException) as exc:
        raise ValueError("invalid preflight plist") from exc
    if (type(config) is not dict or config.get("Label") != _LABEL
            or type(config.get("EnvironmentVariables")) is not dict):
        raise ValueError("invalid preflight plist")
    env = config["EnvironmentVariables"]
    profiles = [parts for line in profile_listing.splitlines()
                if (parts := line.split()) and parts[0] == _PROFILE]
    checks = {
        "cron_disabled": env.get("AOS_QYH_CRON_ENABLED") == "false",
        "snapshot_disabled": env.get("AOS_SNAPSHOT_GROUP_WORKER_ENABLED") == "false",
        "host_disabled": env.get("AOS_EXTENSION_RUNTIME_HOST_ENABLED") == "0",
        "migration_disabled": env.get("AOS_DB_MIGRATION_MODE") == "disabled",
        "launchd_quiesced": not any(
            line.split() and line.split()[-1] == _LABEL
            for line in launchd_listing.splitlines()),
        "port_8080_free": port_8080_open is False,
        "port_18181_free": port_18181_open is False,
        "profile_stopped": len(profiles) == 1 and len(profiles[0]) >= 2
                           and profiles[0][1] == "Stopped",
        "container_policy_proven": container_policy_proven is True,
    }
    return {"verdict": "PREFLIGHT_CANDIDATE_ONLY" if all(checks.values()) else "STOP",
            "checks": checks, "authorizes_profile_start": False}


def _output(command: list[str]) -> str:
    result = subprocess.run(command, text=True, capture_output=True, timeout=5,
                            check=False)
    if result.returncode != 0:
        raise RuntimeError("preflight observation failed")
    return result.stdout


def _port_open(port: int) -> bool:
    result = subprocess.run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
                            text=True, capture_output=True, timeout=5, check=False)
    if result.returncode not in (0, 1) or (result.returncode == 1 and result.stderr):
        raise RuntimeError("preflight observation failed")
    return result.returncode == 0


def collect(plist_path: Path) -> dict:
    return evaluate(plist_path.read_bytes(), launchd_listing=_output(["launchctl", "list"]),
                    port_8080_open=_port_open(8080), port_18181_open=_port_open(18181),
                    profile_listing=_output(["colima", "list"]),
                    container_policy_proven=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plist", type=Path,
                        default=Path.home() / "Library/LaunchAgents/com.aos.a0v-api-8080.plist")
    args = parser.parse_args()
    try:
        result = collect(args.plist)
    except Exception:
        result = {"verdict": "STOP", "checks": {}, "authorizes_profile_start": False,
                  "inspection_error": True}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["verdict"] == "PREFLIGHT_CANDIDATE_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
