"""190m / 191m / 192m — W4 script + SMTP hooks."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CI = ROOT / "scripts" / "ci"


def test_190m_b_layer_script_exists_and_help():
    script = CI / "accept-idp-b-layer.sh"
    assert script.is_file()
    out = subprocess.run(
        ["bash", str(script), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert out.returncode == 0
    assert "190m" in out.stdout or "B-layer" in out.stdout
    assert "sign-off" in out.stdout.lower() or "签收" in out.stdout or "NOT" in out.stdout


def test_190m_b_layer_fails_without_token():
    script = CI / "accept-idp-b-layer.sh"
    env = {**os.environ}
    env.pop("AOS_PROBE_TOKEN", None)
    env.pop("AOS_PROBE_TOKEN_FILE", None)
    env.pop("AOS_OIDC_ISSUER", None)
    env.pop("AOS_OIDC_JWKS_URL", None)
    out = subprocess.run(
        ["bash", str(script)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert out.returncode != 0
    assert "FAIL" in (out.stdout + out.stderr)
    assert "token" in (out.stdout + out.stderr).lower()


def test_191m_ferry_drill_script_help_and_report():
    script = CI / "drill-ferry-airgap.sh"
    assert script.is_file()
    help_out = subprocess.run(
        ["bash", str(script), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert help_out.returncode == 0
    assert "191m" in help_out.stdout or "NOT" in help_out.stdout
    drill = subprocess.run(
        ["bash", str(script), "--skip-curl", "--require-report"],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert drill.returncode == 0, drill.stdout + drill.stderr
    assert "report:" in drill.stdout
    report_dir = ROOT / "deploy" / "dev" / "_ferry_drill"
    assert report_dir.is_dir()
    reports = list(report_dir.glob("drill-*.md"))
    assert reports, "expected drill report"
    text = reports[0].read_text(encoding="utf-8")
    assert "191m" in text or "演练" in text
    assert "签收" in text or "sign-off" in text.lower() or "NOT" in text
