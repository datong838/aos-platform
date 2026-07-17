"""Load aos-platform/.env into process env (no python-dotenv dependency)."""
from __future__ import annotations

import os
from pathlib import Path

_LOADED = False


def _candidate_paths() -> list[Path]:
    here = Path(__file__).resolve()
    # .../services/aos-api/aos_api/env_load.py → aos-platform/
    aos_platform = here.parents[3]
    return [
        aos_platform / ".env",
        aos_platform / "deploy" / "dev" / ".env",
        aos_platform / "deploy" / "dev" / ".secrets.env",
        Path.cwd() / ".env",
    ]


def load_dotenv(force: bool = False) -> Path | None:
    global _LOADED
    if _LOADED and not force:
        return None
    for path in _candidate_paths():
        if not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if not key:
                continue
            # .env is Dev source of truth for AGNES_* / AOS_LLM_* / AOS_S3_* / MINIO_* / AOS_OCR_* when value present
            if key.startswith(
                ("AGNES_", "AOS_LLM_", "AOS_LITELLM_", "AOS_S3_", "MINIO_", "AOS_MYSQL_", "MYSQL_", "AOS_OCR_")
            ) and val:
                os.environ[key] = val
            elif key not in os.environ or os.environ.get(key) == "":
                os.environ[key] = val
        _LOADED = True
        return path
    _LOADED = True
    return None
