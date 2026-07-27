"""Phase 4 · Ontology Action 引擎.

actions CRUD。
模式：Singleton + Pydantic + threading.Lock。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

_LOCK = threading.Lock()


class ActionParam(BaseModel):
    name: str
    datatype: str = "string"
    required: bool = True
    default: Any = None
    description: str = ""


class OntologyAction(BaseModel):
    id: str = Field(default_factory=lambda: "act-" + uuid.uuid4().hex[:8])
    name: str
    display_name: str = ""
    description: str = ""
    object_type_id: str = ""
    params: list[ActionParam] = Field(default_factory=list)
    body: str = ""  # 触发的逻辑（pipeline/function id 或 DSL）
    status: str = "active"  # active|draft|deprecated
    category: str = "writeback"  # writeback|notification|automation
    version: int = 1
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


class ActionEngine:
    """Ontology Action 引擎."""

    _instance: "ActionEngine | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "ActionEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._actions: dict[str, OntologyAction] = {}
                    cls._instance = inst
        return cls._instance

    def create_action(self, name: str, **kwargs: Any) -> OntologyAction:
        with _LOCK:
            act = OntologyAction(name=name, **kwargs)
            self._actions[act.id] = act
            return act

    def get_action(self, action_id: str) -> OntologyAction | None:
        return self._actions.get(action_id)

    def list_actions(self, status: str | None = None, category: str | None = None) -> list[OntologyAction]:
        items = list(self._actions.values())
        if status:
            items = [a for a in items if a.status == status]
        if category:
            items = [a for a in items if a.category == category]
        return items

    def update_action(self, action_id: str, **kwargs: Any) -> OntologyAction:
        with _LOCK:
            act = self._actions.get(action_id)
            if act is None:
                raise KeyError(f"Action {action_id} not found")
            for k, v in kwargs.items():
                if hasattr(act, k) and k != "id":
                    setattr(act, k, v)
            act.version += 1
            act.updated_at = time.time()
            return act

    def delete_action(self, action_id: str) -> bool:
        with _LOCK:
            return self._actions.pop(action_id, None) is not None

    def reset(self) -> None:
        with _LOCK:
            self._actions.clear()


def get_action_engine() -> ActionEngine:
    return ActionEngine()
