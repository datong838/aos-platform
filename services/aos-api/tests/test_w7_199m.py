"""199m — desktop update drill script hooks."""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CI = ROOT / "scripts" / "ci"


def test_199m_drill_desktop_update_script():
    script = CI / "drill-desktop-update.sh"
    assert script.is_file()
    help_out = subprocess.run(
        ["bash", str(script), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert help_out.returncode == 0
    assert "199m" in help_out.stdout or "NOT" in help_out.stdout
    drill = subprocess.run(
        ["bash", str(script), "--require-report"],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert drill.returncode == 0, drill.stdout + drill.stderr
    assert "report:" in drill.stdout
    report_dir = ROOT / "deploy" / "dev" / "_desktop_update_drill"
    reports = list(report_dir.glob("drill-*.md"))
    assert reports
    text = reports[0].read_text(encoding="utf-8")
    assert "199m" in text
    assert "签收" in text or "sign" in text.lower()
