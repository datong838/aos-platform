"""Unit tests for LiteLLM sidecar .env discovery (no Docker required)."""
from __future__ import annotations

from pathlib import Path

from app import _env_file_candidates


def test_docker_layout_no_index_error(tmp_path: Path):
    """Simulate /app/app.py — parents shorter than 3 must not raise."""
    app_py = tmp_path / "app.py"
    app_py.write_text("# stub\n", encoding="utf-8")
    cands = _env_file_candidates(app_py)
    assert cands
    assert all(isinstance(p, Path) for p in cands)
    # shallow tree: only parent dirs that exist
    assert (tmp_path / ".env") in cands or any(p.name == ".env" for p in cands)


def test_host_layout_includes_repo_root(tmp_path: Path):
    """deploy/dev/litellm/app.py → aos-platform/.env is candidates[parents[3]]."""
    root = tmp_path / "aos-platform"
    litellm = root / "deploy" / "dev" / "litellm"
    litellm.mkdir(parents=True)
    app_py = litellm / "app.py"
    app_py.write_text("# stub\n", encoding="utf-8")
    (root / ".env").write_text("AGNES_API_KEY=x\n", encoding="utf-8")
    cands = _env_file_candidates(app_py)
    assert root / ".env" in cands
