"""Phase 4 · Ontology Wiki 引擎.

wikis CRUD + versions + diff。
模式：Singleton + Pydantic + threading.Lock。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

_LOCK = threading.Lock()


class WikiVersion(BaseModel):
    id: str = Field(default_factory=lambda: "wv-" + uuid.uuid4().hex[:6])
    wiki_id: str
    version: int
    content: str = ""
    title: str = ""
    widgets: list[dict[str, Any]] = Field(default_factory=list)
    variables: dict[str, Any] = Field(default_factory=dict)
    author: str = "system"
    message: str = ""
    created_at: float = Field(default_factory=lambda: time.time())


class Wiki(BaseModel):
    id: str = Field(default_factory=lambda: "wiki-" + uuid.uuid4().hex[:8])
    title: str
    content: str = ""
    object_type_id: str = ""
    tags: list[str] = Field(default_factory=list)
    widgets: list[dict[str, Any]] = Field(default_factory=list)
    variables: dict[str, Any] = Field(default_factory=dict)
    author: str = "system"
    version: int = 1
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


class WikiEngine:
    """Ontology Wiki 引擎."""

    _instance: "WikiEngine | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "WikiEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._wikis: dict[str, Wiki] = {}
                    inst._versions: dict[str, list[WikiVersion]] = {}
                    cls._instance = inst
        return cls._instance

    # ── Wiki CRUD ──
    def create_wiki(self, title: str, **kwargs: Any) -> Wiki:
        with _LOCK:
            wiki = Wiki(title=title, **kwargs)
            self._wikis[wiki.id] = wiki
            # 初始版本
            v0 = WikiVersion(
                wiki_id=wiki.id,
                version=1,
                content=wiki.content,
                title=wiki.title,
                widgets=wiki.widgets,
                variables=wiki.variables,
                author=wiki.author,
                message="Initial version",
            )
            self._versions.setdefault(wiki.id, []).append(v0)
            return wiki

    def get_wiki(self, wiki_id: str) -> Wiki | None:
        return self._wikis.get(wiki_id)

    def list_wikis(self, search: str | None = None, tag: str | None = None) -> list[Wiki]:
        items = list(self._wikis.values())
        if search:
            s = search.lower()
            items = [w for w in items if s in w.title.lower() or s in w.content.lower()]
        if tag:
            items = [w for w in items if tag in w.tags]
        return items

    def update_wiki(self, wiki_id: str, expected_version: int | None = None, **kwargs: Any) -> Wiki:
        with _LOCK:
            wiki = self._wikis.get(wiki_id)
            if wiki is None:
                raise KeyError(f"Wiki {wiki_id} not found")
            if expected_version is not None and wiki.version != expected_version:
                raise ValueError(f"Wiki {wiki_id} version conflict")
            old_content = wiki.content
            old_title = wiki.title
            for k, v in kwargs.items():
                if hasattr(wiki, k) and k != "id":
                    setattr(wiki, k, v)
            wiki.version += 1
            wiki.updated_at = time.time()
            # 记录版本
            new_version = WikiVersion(
                wiki_id=wiki_id,
                version=wiki.version,
                content=wiki.content,
                title=wiki.title,
                widgets=wiki.widgets,
                variables=wiki.variables,
                author=wiki.author,
                message=kwargs.get("message", f"Update v{wiki.version}"),
            )
            self._versions.setdefault(wiki_id, []).append(new_version)
            return wiki

    def delete_wiki(self, wiki_id: str) -> bool:
        with _LOCK:
            self._versions.pop(wiki_id, None)
            return self._wikis.pop(wiki_id, None) is not None

    # ── Versions ──
    def list_versions(self, wiki_id: str) -> list[WikiVersion]:
        return list(self._versions.get(wiki_id, []))

    def get_version(self, wiki_id: str, version: int) -> WikiVersion | None:
        for v in self._versions.get(wiki_id, []):
            if v.version == version:
                return v
        return None

    # ── Diff ──
    def diff(self, wiki_id: str, from_version: int, to_version: int) -> dict[str, Any]:
        v_from = self.get_version(wiki_id, from_version)
        v_to = self.get_version(wiki_id, to_version)
        if v_from is None or v_to is None:
            raise KeyError(f"Version not found for wiki {wiki_id}")
        from_lines = v_from.content.splitlines() if v_from.content else []
        to_lines = v_to.content.splitlines() if v_to.content else []
        # 简易 diff
        added = [l for l in to_lines if l not in from_lines]
        removed = [l for l in from_lines if l not in to_lines]
        title_changed = v_from.title != v_to.title
        return {
            "wiki_id": wiki_id,
            "from_version": from_version,
            "to_version": to_version,
            "title_changed": title_changed,
            "from_title": v_from.title,
            "to_title": v_to.title,
            "from_content": v_from.content,
            "to_content": v_to.content,
            "added_lines": added,
            "removed_lines": removed,
            "added_count": len(added),
            "removed_count": len(removed),
        }

    def reset(self) -> None:
        with _LOCK:
            self._wikis.clear()
            self._versions.clear()


def get_wiki_engine() -> WikiEngine:
    return WikiEngine()
