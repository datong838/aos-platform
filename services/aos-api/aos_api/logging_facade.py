"""Unified Logger facade — T-CROSS §3.2 (Wave-0 minimal)."""
from __future__ import annotations

import json
import logging
import os
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

_trace_id: ContextVar[str] = ContextVar("trace_id", default="-")
_org_id: ContextVar[str] = ContextVar("org_id", default="-")
_project_id: ContextVar[str] = ContextVar("project_id", default="-")

# Reserved: Audit channel must not be gated by AOS_LOG_LEVEL (T-CROSS).
_audit_logger = logging.getLogger("aos.audit")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "service": "aos-api",
            "logger": record.name,
            "msg": record.getMessage(),
            "trace_id": getattr(record, "trace_id", _trace_id.get()),
            "org_id": getattr(record, "org_id", _org_id.get()),
            "project_id": getattr(record, "project_id", _project_id.get()),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = _trace_id.get()  # type: ignore[attr-defined]
        record.org_id = _org_id.get()  # type: ignore[attr-defined]
        record.project_id = _project_id.get()  # type: ignore[attr-defined]
        return True


def _level_from_env() -> int:
    name = os.getenv("AOS_LOG_LEVEL", "debug").lower()
    return {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warn": logging.WARNING,
        "warning": logging.WARNING,
        "error": logging.ERROR,
    }.get(name, logging.DEBUG)


_configured = False


def configure_logging() -> None:
    global _configured
    if _configured:
        return
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    fmt = os.getenv("AOS_LOG_FORMAT", "json").lower()
    if fmt == "pretty":
        handler.setFormatter(
            logging.Formatter(
                "%(levelname)s trace=%(trace_id)s %(name)s %(message)s"
            )
        )
    else:
        handler.setFormatter(JsonFormatter())
    handler.addFilter(ContextFilter())
    root.addHandler(handler)
    root.setLevel(_level_from_env())
    _audit_logger.setLevel(logging.INFO)
    _configured = True


def set_context(*, trace_id: str, org_id: str, project_id: str) -> None:
    _trace_id.set(trace_id)
    _org_id.set(org_id)
    _project_id.set(project_id)


def reset_context() -> None:
    _trace_id.set("-")
    _org_id.set("-")
    _project_id.set("-")


def get_trace_id() -> str:
    return _trace_id.get()


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)


def audit(event: str, **fields: Any) -> None:
    """Audit channel — independent of AOS_LOG_LEVEL gating intent."""
    configure_logging()
    _audit_logger.info("audit event=%s fields=%s", event, fields)
