"""Phase 4 · Ontology Link 引擎.

link types + link instances CRUD。
模式：Singleton + Pydantic + threading.Lock。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

_LOCK = threading.Lock()


class LinkType(BaseModel):
    id: str = Field(default_factory=lambda: "lt-" + uuid.uuid4().hex[:8])
    name: str
    display_name: str = ""
    source_object_type_id: str = ""
    target_object_type_id: str = ""
    cardinality: str = "one_to_many"  # one_to_one|one_to_many|many_to_many
    description: str = ""
    created_at: float = Field(default_factory=lambda: time.time())


class LinkInstance(BaseModel):
    id: str = Field(default_factory=lambda: "li-" + uuid.uuid4().hex[:8])
    link_type_id: str
    source_object_id: str
    target_object_id: str
    properties: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


class LinkEngine:
    """Ontology Link 引擎."""

    _instance: "LinkEngine | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "LinkEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._link_types: dict[str, LinkType] = {}
                    inst._link_instances: dict[str, LinkInstance] = {}
                    cls._instance = inst
        return cls._instance

    # ── Link Types ──
    def create_link_type(self, name: str, **kwargs: Any) -> LinkType:
        with _LOCK:
            lt = LinkType(name=name, **kwargs)
            self._link_types[lt.id] = lt
            return lt

    def get_link_type(self, lt_id: str) -> LinkType | None:
        return self._link_types.get(lt_id)

    def list_link_types(self) -> list[LinkType]:
        return list(self._link_types.values())

    def update_link_type(self, lt_id: str, **kwargs: Any) -> LinkType:
        with _LOCK:
            lt = self._link_types.get(lt_id)
            if lt is None:
                raise KeyError(f"LinkType {lt_id} not found")
            for k, v in kwargs.items():
                if hasattr(lt, k) and k != "id":
                    setattr(lt, k, v)
            return lt

    def delete_link_type(self, lt_id: str) -> bool:
        with _LOCK:
            self._link_instances = {
                k: v for k, v in self._link_instances.items() if v.link_type_id != lt_id
            }
            return self._link_types.pop(lt_id, None) is not None

    # ── Link Instances ──
    def create_link(self, link_type_id: str, source_object_id: str, target_object_id: str, **kwargs: Any) -> LinkInstance:
        with _LOCK:
            if link_type_id not in self._link_types:
                raise KeyError(f"LinkType {link_type_id} not found")
            li = LinkInstance(
                link_type_id=link_type_id,
                source_object_id=source_object_id,
                target_object_id=target_object_id,
                **kwargs,
            )
            self._link_instances[li.id] = li
            return li

    def get_link(self, link_id: str) -> LinkInstance | None:
        return self._link_instances.get(link_id)

    def list_links(self, link_type_id: str | None = None) -> list[LinkInstance]:
        items = list(self._link_instances.values())
        if link_type_id:
            items = [l for l in items if l.link_type_id == link_type_id]
        return items

    def update_link(self, link_id: str, **kwargs: Any) -> LinkInstance:
        with _LOCK:
            li = self._link_instances.get(link_id)
            if li is None:
                raise KeyError(f"Link {link_id} not found")
            for k, v in kwargs.items():
                if hasattr(li, k) and k != "id":
                    setattr(li, k, v)
            li.updated_at = time.time()
            return li

    def delete_link(self, link_id: str) -> bool:
        with _LOCK:
            return self._link_instances.pop(link_id, None) is not None

    def reset(self) -> None:
        with _LOCK:
            self._link_types.clear()
            self._link_instances.clear()


def get_link_engine() -> LinkEngine:
    return LinkEngine()
