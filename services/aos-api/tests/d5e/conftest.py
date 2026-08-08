"""
D5-E0/D5-E1/D5-E2 conftest — evidence metadata, fixtures, pytest markers.

Level mapping (_THIS_DIR = tests/d5e/, counting upward):
  parents[0] = tests/
  parents[1] = services/aos-api/
  parents[2] = services/
  parents[3] = aos-platform/
  parents[4] = ai_agent/  <-- project root
"""

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _THIS_DIR.parents[4]           # ai_agent/
AOS_PLATFORM = _THIS_DIR.parents[3]           # aos-platform/

DOCS_ROOT = PROJECT_ROOT / "docs"
_DWAVES = DOCS_ROOT / "palantier" / "20_tech" / "电商平台接入" / "微商城电商接入方案" / "D-waves"

D5E_DOC_PATH = _DWAVES / "D5-E-G17G18G19证据闭合方案.md"
O1_DOC_PATH = _DWAVES / "O1-本体数字孪生层改造方案.md"
D4_DOC_PATH = _DWAVES / "D4-12OT业务闭环与302表衔接执行规格.md"

EVIDENCE_DIR = _THIS_DIR / "evidence"

# DB connection (Docker container aos-dev-pg)
DB_URL = os.environ.get(
    "AOS_DB_URL",
    "postgresql+psycopg://aos_app:aos_dev_only_change_me@localhost:5433/aos_meta",
)

TENANT_SCOPE = {"org_id": "org-org", "workspace_id": "dev-project"}


# ---------------------------------------------------------------------------
# pytest markers
# ---------------------------------------------------------------------------

def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "write: tests that perform writes (DLQ injection, canary, migrations, etc.)",
    )


# ---------------------------------------------------------------------------
# Hash helpers
# ---------------------------------------------------------------------------

def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(AOS_PLATFORM),
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "UNKNOWN"


def _git_short_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(AOS_PLATFORM),
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "UNKNOWN"


def _file_sha256(path: Path) -> str:
    if not path.exists():
        return "FILE_NOT_FOUND"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _deterministic_hash(payload) -> str:
    """Canonical JSON SHA-256 without default=str."""
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Evidence collection
# ---------------------------------------------------------------------------

def collect_evidence_metadata(phase: str = "D5-E0") -> dict:
    """Collect immutable metadata for an evidence snapshot."""
    return {
        "phase": phase,
        "git_sha": _git_sha(),
        "git_short_sha": _git_short_sha(),
        "doc_version": "D5-E-v2.9",
        "doc_sha256": _file_sha256(D5E_DOC_PATH),
        "o1_doc_sha256": _file_sha256(O1_DOC_PATH),
        "d4_doc_sha256": _file_sha256(D4_DOC_PATH),
        "alembic_revision": _alembic_revision(),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "ended_at": None,
        "tenant_scope": f"{TENANT_SCOPE['org_id']}/{TENANT_SCOPE['workspace_id']}",
        "db_url_hash": "sha256:" + hashlib.sha256(
            DB_URL.split("@")[-1].encode()
        ).hexdigest()[:16],
    }


def _alembic_revision() -> str:
    try:
        engine = create_engine(DB_URL)
        with engine.connect() as conn:
            r = conn.execute(
                text("SELECT version_num FROM alembic_version ORDER BY version_num DESC LIMIT 1")
            )
            row = r.fetchone()
            engine.dispose()
            return row[0] if row else "NONE"
    except Exception:
        return "UNAVAILABLE"


def save_evidence(gate: str, phase: str, results: dict, meta: dict | None = None):
    """Write evidence JSON to evidence/ directory."""
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"{phase}_{gate}_{ts}.json"
    filepath = EVIDENCE_DIR / filename

    if meta is None:
        meta = collect_evidence_metadata(phase)

    meta["ended_at"] = datetime.now(timezone.utc).isoformat()

    evidence = {
        **meta,
        "gate": gate,
        "results": results,
    }
    filepath.write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return filepath


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def db_engine():
    engine = create_engine(DB_URL)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def db_conn(db_engine):
    with db_engine.connect() as conn:
        yield conn


@pytest.fixture(scope="session")
def evidence_meta():
    return collect_evidence_metadata("D5-E0")


@pytest.fixture(scope="session")
def tenant_scope():
    return TENANT_SCOPE.copy()
