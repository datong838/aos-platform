"""W1-14 · Pipeline Builder 交互式 DAG 编辑器。

Pipeline DAG 模型 + 命令式编辑（增删改节点/边）+ 撤销/重做栈 +
校验（环检测复用 W1-13 LineageGraph）+ 预览执行（复用 W1-8 transform_ops）。

详见 docs/palantier/20_tech/220tech_pipeline-builder-dag.md。
"""
from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from .lineage_graph import LineageGraph, LineageNode
from .transform_ops import TRANSFORM_REGISTRY, apply_transform


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


MAX_UNDO = 50


class PipelineNode(BaseModel):
    id: str
    kind: Literal["dataset", "transform", "llm", "media_set"] = "dataset"
    label: str = ""
    op: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    dataset_rid: str | None = None
    media_set_id: str | None = None


class PipelineEdge(BaseModel):
    src: str
    dst: str


class Pipeline(BaseModel):
    id: str
    name: str
    nodes: list[PipelineNode] = Field(default_factory=list)
    edges: list[PipelineEdge] = Field(default_factory=list)
    version: int = 1
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class PipelineEditorError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class PipelineEditor:
    def __init__(self, pipeline: Pipeline | None = None) -> None:
        self.pipeline: Pipeline = pipeline or Pipeline(id=_new_id(), name="untitled")
        self._undo_stack: list[Pipeline] = []
        self._redo_stack: list[Pipeline] = []

    def apply(self, command: dict[str, Any]) -> Pipeline:
        before = self._snapshot()
        try:
            action = command.get("action")
            if action == "batch":
                for sub in command.get("commands", []):
                    self._apply_one(sub)
            else:
                self._apply_one(command)
        except PipelineEditorError:
            self.pipeline = before
            raise
        self.pipeline.version += 1
        self.pipeline.updated_at = _now()
        self._undo_stack.append(before)
        if len(self._undo_stack) > MAX_UNDO:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        return self.pipeline

    def _apply_one(self, command: dict[str, Any]) -> None:
        action = command.get("action")
        handler = getattr(self, f"_do_{action}", None)
        if handler is None:
            raise PipelineEditorError("UNKNOWN_ACTION", f"未知命令 {action!r}")
        handler(command)

    def _snapshot(self) -> Pipeline:
        return copy.deepcopy(self.pipeline)

    def _do_add_node(self, command: dict[str, Any]) -> None:
        node_data = command.get("node") or {}
        node_id = node_data.get("id") or _new_id()
        if any(n.id == node_id for n in self.pipeline.nodes):
            raise PipelineEditorError("NODE_DUP_ID", f"节点 id {node_id!r} 已存在")
        node = PipelineNode(**{**node_data, "id": node_id})
        self._validate_node(node)
        self.pipeline.nodes.append(node)

    def _do_remove_node(self, command: dict[str, Any]) -> None:
        node_id = command.get("node_id")
        if not any(n.id == node_id for n in self.pipeline.nodes):
            raise PipelineEditorError("NODE_NOT_FOUND", f"节点 {node_id!r} 不存在")
        self.pipeline.nodes = [n for n in self.pipeline.nodes if n.id != node_id]
        self.pipeline.edges = [
            e for e in self.pipeline.edges if e.src != node_id and e.dst != node_id
        ]

    def _do_update_node(self, command: dict[str, Any]) -> None:
        node_id = command.get("node_id")
        patch = command.get("patch") or {}
        target = None
        for n in self.pipeline.nodes:
            if n.id == node_id:
                target = n
                break
        if target is None:
            raise PipelineEditorError("NODE_NOT_FOUND", f"节点 {node_id!r} 不存在")
        updated = target.model_copy(update=patch)
        self._validate_node(updated)
        for i, n in enumerate(self.pipeline.nodes):
            if n.id == node_id:
                self.pipeline.nodes[i] = updated
                break

    def _do_add_edge(self, command: dict[str, Any]) -> None:
        edge_data = command.get("edge") or {}
        edge = PipelineEdge(**edge_data)
        if edge.src == edge.dst:
            raise PipelineEditorError("EDGE_SELF_LOOP", "不允许自环")
        if not any(n.id == edge.src for n in self.pipeline.nodes):
            raise PipelineEditorError("EDGE_SRC_MISSING", f"src 节点 {edge.src!r} 不存在")
        if not any(n.id == edge.dst for n in self.pipeline.nodes):
            raise PipelineEditorError("EDGE_DST_MISSING", f"dst 节点 {edge.dst!r} 不存在")
        if any(e.src == edge.src and e.dst == edge.dst for e in self.pipeline.edges):
            return
        self.pipeline.edges.append(edge)
        if self._has_cycle():
            self.pipeline.edges.pop()
            raise PipelineEditorError("CYCLE_DETECTED", "添加该边会形成环")

    def _do_remove_edge(self, command: dict[str, Any]) -> None:
        edge_data = command.get("edge") or {}
        edge = PipelineEdge(**edge_data)
        before = len(self.pipeline.edges)
        self.pipeline.edges = [
            e for e in self.pipeline.edges if not (e.src == edge.src and e.dst == edge.dst)
        ]
        if len(self.pipeline.edges) == before:
            raise PipelineEditorError("EDGE_NOT_FOUND", f"边 {edge.src}→{edge.dst} 不存在")

    def _validate_node(self, node: PipelineNode) -> None:
        if node.kind == "transform":
            if not node.op:
                raise PipelineEditorError("TRANSFORM_NO_OP", "transform 节点必须指定 op")
            if node.op.startswith("python:"):
                from .functions_python_builder import get_builder
                fn_name = node.op[len("python:"):]
                try:
                    get_builder().get(fn_name)
                except Exception as exc:
                    raise PipelineEditorError(
                        "PYTHON_FUNC_NOT_FOUND", f"python 函数 {fn_name!r} 未注册"
                    ) from exc
                return
            if node.op not in TRANSFORM_REGISTRY:
                raise PipelineEditorError(
                    "TRANSFORM_BAD_OP",
                    f"未知算子 {node.op!r}，可用：{sorted(TRANSFORM_REGISTRY.keys())}",
                )
        elif node.kind == "dataset":
            if not node.dataset_rid and not node.label:
                raise PipelineEditorError(
                    "DATASET_NO_RID", "dataset 节点必须指定 dataset_rid 或 label"
                )
        elif node.kind == "llm":
            if not node.config.get("template"):
                raise PipelineEditorError(
                    "LLM_NO_TEMPLATE", "llm 节点必须指定 config.template（AIP 模板）"
                )
        elif node.kind == "media_set":
            if not node.media_set_id:
                raise PipelineEditorError(
                    "MEDIA_SET_NO_ID", "media_set 节点必须指定 media_set_id"
                )

    def _has_cycle(self) -> bool:
        graph = LineageGraph()
        for n in self.pipeline.nodes:
            graph.add_node(LineageNode(id=n.id, type="dataset", name=n.label))
        for e in self.pipeline.edges:
            graph.add_edge(e.src, e.dst)
        return graph.has_cycle()

    def undo(self) -> Pipeline:
        if not self._undo_stack:
            raise PipelineEditorError("UNDO_EMPTY", "无可撤销操作")
        self._redo_stack.append(self._snapshot())
        self.pipeline = self._undo_stack.pop()
        return self.pipeline

    def redo(self) -> Pipeline:
        if not self._redo_stack:
            raise PipelineEditorError("REDO_EMPTY", "无可重做操作")
        self._undo_stack.append(self._snapshot())
        self.pipeline = self._redo_stack.pop()
        return self.pipeline

    def validate(self) -> list[str]:
        errors: list[str] = []
        node_ids = {n.id for n in self.pipeline.nodes}
        for n in self.pipeline.nodes:
            if n.kind == "transform" and not n.op:
                errors.append(f"TRANSFORM_NO_OP: 节点 {n.id} 缺少 op")
            elif n.kind == "transform" and n.op.startswith("python:"):
                from .functions_python_builder import get_builder
                fn_name = n.op[len("python:"):]
                try:
                    get_builder().get(fn_name)
                except Exception:
                    errors.append(f"PYTHON_FUNC_NOT_FOUND: 节点 {n.id} 引用未注册函数 {fn_name!r}")
            elif n.kind == "transform" and n.op not in TRANSFORM_REGISTRY:
                errors.append(f"TRANSFORM_BAD_OP: 节点 {n.id} 算子 {n.op!r} 未注册")
            elif n.kind == "dataset" and not n.dataset_rid and not n.label:
                errors.append(f"DATASET_NO_RID: 节点 {n.id} 缺少 dataset_rid/label")
            elif n.kind == "llm" and not n.config.get("template"):
                errors.append(f"LLM_NO_TEMPLATE: 节点 {n.id} 缺少 config.template")
            elif n.kind == "media_set" and not n.media_set_id:
                errors.append(f"MEDIA_SET_NO_ID: 节点 {n.id} 缺少 media_set_id")
        for e in self.pipeline.edges:
            if e.src == e.dst:
                errors.append(f"EDGE_SELF_LOOP: {e.src}→{e.dst}")
            if e.src not in node_ids:
                errors.append(f"EDGE_SRC_MISSING: {e.src}")
            if e.dst not in node_ids:
                errors.append(f"EDGE_DST_MISSING: {e.dst}")
        if self._has_cycle():
            errors.append("CYCLE_DETECTED: 图中存在环")
        return errors

    def preview(self, inputs: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
        errors = self.validate()
        if errors:
            raise PipelineEditorError("VALIDATION_FAILED", "; ".join(errors))
        order = self._topological_order()
        outputs: dict[str, list[dict[str, Any]]] = {}
        upstream_map: dict[str, list[str]] = {}
        for e in self.pipeline.edges:
            upstream_map.setdefault(e.dst, []).append(e.src)
        for nid in order:
            node = next(n for n in self.pipeline.nodes if n.id == nid)
            if node.kind == "dataset":
                outputs[nid] = list(inputs.get(nid, []))
                continue
            if node.kind == "media_set":
                from .media_set import get_store as _get_ms_store
                outputs[nid] = _get_ms_store().get_rows(node.media_set_id or "")
                continue
            merged: list[dict[str, Any]] = []
            for src in upstream_map.get(nid, []):
                merged.extend(outputs.get(src, []))
            outputs[nid] = self._apply_node_op(node, merged)
        return outputs

    def _apply_node_op(self, node: PipelineNode, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if node.kind == "llm":
            from .aip_nodes import execute_llm_node
            return execute_llm_node(rows, node.config)
        op = node.op or ""
        if op.startswith("python:"):
            from .functions_python_builder import get_builder
            return get_builder().call_raw(op[len("python:"):], rows)
        return apply_transform(op, rows, node.config)

    def _topological_order(self) -> list[str]:
        graph = LineageGraph()
        for n in self.pipeline.nodes:
            graph.add_node(LineageNode(id=n.id, type="dataset", name=n.label))
        for e in self.pipeline.edges:
            graph.add_edge(e.src, e.dst)
        try:
            return graph.topological_sort()
        except Exception as exc:
            raise PipelineEditorError("CYCLE_DETECTED", str(exc)) from exc


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


class PipelineStore:
    def __init__(self) -> None:
        self._editors: dict[str, PipelineEditor] = {}

    def create(self, name: str) -> Pipeline:
        pid = _new_id()
        pipeline = Pipeline(id=pid, name=name)
        self._editors[pid] = PipelineEditor(pipeline)
        return pipeline

    def list_all(self) -> list[Pipeline]:
        return [ed.pipeline for ed in self._editors.values()]

    def get(self, pid: str) -> Pipeline:
        return self._require(pid).pipeline

    def editor(self, pid: str) -> PipelineEditor:
        return self._require(pid)

    def delete(self, pid: str) -> None:
        if pid not in self._editors:
            raise PipelineEditorError("NOT_FOUND", f"Pipeline {pid!r} 不存在")
        del self._editors[pid]

    def _require(self, pid: str) -> PipelineEditor:
        if pid not in self._editors:
            raise PipelineEditorError("NOT_FOUND", f"Pipeline {pid!r} 不存在")
        return self._editors[pid]


_store = PipelineStore()


def get_store() -> PipelineStore:
    return _store
