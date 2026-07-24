"""W2-AE · AIP 辅助与仓库配置组（#107 / #108 / #110）.

- #107 AIPAssistEngine：代码辅助请求（explain/vulnerability/translate/complete）
- #108 RepoSettingsEngine：仓库配置文件（标签验证/PR 模板/验证规则）
- #110 ProjectStructureEngine：推荐项目结构模板（Datasource→Transform→Ontology→Workflow）

详见 docs/palantier/20_tech/220tech_w2-ae-aip-assist.md。
"""
from __future__ import annotations

import re
import threading
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

# ════════════════════ 常量 ════════════════════

_VALID_ASSIST_KINDS = {"explain", "vulnerability", "translate", "complete"}
_VALID_ASSIST_LANGUAGES = {"python", "java", "typescript", "sql"}
_VALID_ASSIST_STATUSES = {"pending", "running", "completed", "error"}

_VALID_RULE_KINDS = {"branch_protection", "required_reviewers", "status_check", "path_filter"}

_VALID_LAYERS = {"datasource", "transform", "ontology", "workflow"}
_VALID_COMPONENT_TYPES = {"dataset", "transform", "ontology", "workflow", "metric"}

_MAX_REQUESTS = 200
_MAX_SETTINGS = 200
_MAX_STRUCTURES = 200
_MAX_RESULTS = 200

# vulnerability 扫描的危险内置（与 dev_tooling._BANNED_BUILTINS 保持一致）
_DANGEROUS_BUILTINS = (
    "open", "eval", "exec", "compile", "__import__",
    "globals", "locals", "vars", "getattr", "setattr", "delattr",
    "memoryview", "breakpoint", "exit", "quit",
)


# ════════════════════ 数据模型 ════════════════════

class AIPAssistRequest(BaseModel):
    """AIP 代码辅助请求。"""
    id: str = Field(default_factory=lambda: "aip-" + uuid.uuid4().hex[:10])
    kind: str                            # explain / vulnerability / translate / complete
    code: str
    language: str = "python"             # python / java / typescript / sql
    context: str = ""
    status: str = "pending"              # pending / running / completed / error
    result: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=lambda: time.time())
    completed_at: float = 0.0


class RepoSettings(BaseModel):
    """仓库配置文件（repoSettings.json）。"""
    id: str = Field(default_factory=lambda: "rs-" + uuid.uuid4().hex[:10])
    repo_id: str
    label_validation: dict[str, Any] = Field(default_factory=dict)
    pr_template: str = ""
    validation_rules: list[dict[str, Any]] = Field(default_factory=list)
    enforce_branch_protection: bool = False
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


class StructureComponent(BaseModel):
    """结构组件。"""
    layer: str                            # datasource / transform / ontology / workflow
    name: str
    type: str                             # dataset / transform / ontology / workflow / metric
    rid_prefix: str = ""
    required: bool = False


class ProjectStructure(BaseModel):
    """推荐项目结构模板。"""
    id: str = Field(default_factory=lambda: "ps-" + uuid.uuid4().hex[:10])
    name: str
    description: str = ""
    layers: list[str] = Field(default_factory=list)
    components: list[StructureComponent] = Field(default_factory=list)
    created_at: float = Field(default_factory=lambda: time.time())


# ════════════════════ 错误 ════════════════════

class AIPAssistError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


# ════════════════════ #107 AIPAssistEngine ════════════════════

class AIPAssistEngine:
    def __init__(self) -> None:
        self._requests: dict[str, AIPAssistRequest] = {}
        self._results: list[AIPAssistRequest] = []
        self._lock = threading.Lock()

    def register(self, req: AIPAssistRequest) -> AIPAssistRequest:
        if not req.code:
            raise AIPAssistError("MISSING_CODE", "代码内容不能为空")
        if req.kind not in _VALID_ASSIST_KINDS:
            raise AIPAssistError("INVALID_KIND", f"未知辅助类型：{req.kind}")
        if req.language not in _VALID_ASSIST_LANGUAGES:
            raise AIPAssistError("INVALID_LANGUAGE", f"未知语言：{req.language}")
        with self._lock:
            if len(self._requests) >= _MAX_REQUESTS:
                oldest_id = next(iter(self._requests))
                self._requests.pop(oldest_id, None)
            self._requests[req.id] = req
        return req

    def get(self, req_id: str) -> AIPAssistRequest:
        r = self._requests.get(req_id)
        if r is None:
            raise AIPAssistError("NOT_FOUND", f"辅助请求 {req_id} 不存在")
        return r

    def list(
        self, kind: str | None = None, status: str | None = None,
    ) -> list[AIPAssistRequest]:
        items = list(self._requests.values())
        if kind:
            items = [r for r in items if r.kind == kind]
        if status:
            items = [r for r in items if r.status == status]
        return items

    def update(self, req_id: str, updates: dict[str, Any]) -> AIPAssistRequest:
        r = self.get(req_id)
        for k, v in updates.items():
            if k in ("id", "created_at", "completed_at"):
                continue
            if hasattr(r, k):
                setattr(r, k, v)
        return r

    def delete(self, req_id: str) -> bool:
        return self._requests.pop(req_id, None) is not None

    def run(self, req_id: str) -> AIPAssistRequest:
        r = self.get(req_id)
        if r.status == "completed":
            raise AIPAssistError("ALREADY_COMPLETED", f"请求 {req_id} 已完成，不可重复 run")
        r.status = "running"
        try:
            r.result = self._dispatch(r)
            r.status = "completed"
            r.completed_at = time.time()
        except AIPAssistError:
            raise
        except Exception as exc:  # noqa: BLE001
            r.status = "error"
            r.result = {"error": str(exc)}
            r.completed_at = time.time()
        with self._lock:
            if len(self._results) >= _MAX_RESULTS:
                self._results.pop(0)
            self._results.append(r)
        return r

    def _dispatch(self, req: AIPAssistRequest) -> dict[str, Any]:
        if req.kind == "explain":
            return self._explain(req)
        if req.kind == "vulnerability":
            return self._vulnerability(req)
        if req.kind == "translate":
            return self._translate(req)
        if req.kind == "complete":
            return self._complete(req)
        raise AIPAssistError("INVALID_KIND", f"未知辅助类型：{req.kind}")

    def _explain(self, req: AIPAssistRequest) -> dict[str, Any]:
        lines = req.code.splitlines() if req.code else []
        return {
            "summary": f"代码共 {len(lines)} 行，语言 {req.language}",
            "lines": len(lines),
            "language": req.language,
        }

    def _vulnerability(self, req: AIPAssistRequest) -> dict[str, Any]:
        vulns: list[dict[str, Any]] = []
        for i, line in enumerate(req.code.splitlines(), start=1):
            for builtin in _DANGEROUS_BUILTINS:
                # 单词边界匹配，避免误命中子串（如 opener）
                pattern = r"\b" + re.escape(builtin) + r"\s*\("
                if re.search(pattern, line):
                    vulns.append({
                        "line": i,
                        "builtin": builtin,
                        "snippet": line.strip()[:80],
                    })
        return {"vulnerabilities": vulns, "count": len(vulns)}

    def _translate(self, req: AIPAssistRequest) -> dict[str, Any]:
        # 简化映射：python → java（其他语言返回原文）
        target = "java" if req.language == "python" else req.language
        if req.language != "python":
            return {
                "translated": req.code,
                "target_language": target,
                "note": "unsupported source language, returned as-is",
            }
        # 简化关键字映射（演示用，非真实翻译）
        rules = [
            (r"\bdef\s+(\w+)\s*\(([^)]*)\)\s*:", r"public void \1(\2) {"),
            (r"\breturn\s+", "return "),
            (r"\bTrue\b", "true"),
            (r"\bFalse\b", "false"),
            (r"\bNone\b", "null"),
            (r"\bprint\s*\(", "System.out.println("),
        ]
        translated = req.code
        for pat, repl in rules:
            translated = re.sub(pat, repl, translated)
        # 末尾补 } 闭合（粗略）
        if "public void" in translated and not translated.rstrip().endswith("}"):
            translated = translated.rstrip() + "\n}\n"
        return {
            "translated": translated,
            "target_language": target,
        }

    def _complete(self, req: AIPAssistRequest) -> dict[str, Any]:
        code = req.code
        if not code:
            return {"suggestion": ""}
        last_char = code.rstrip()[-1]
        last_line = code.splitlines()[-1].rstrip() if code.splitlines() else ""
        suggestion = ""
        # 简化补全规则
        if last_line.endswith("def "):
            suggestion = "name(self) -> None:\n    pass"
        elif last_line.endswith("if "):
            suggestion = "condition:\n    pass"
        elif last_line.endswith("for "):
            suggestion = "item in items:\n    pass"
        elif last_char == "(":
            suggestion = ")"
        elif last_char == "[":
            suggestion = "]"
        elif last_char == "{":
            suggestion = "}"
        elif last_char == '"':
            suggestion = '"'
        else:
            # 末行缩进延续
            indent = re.match(r"^(\s*)", last_line).group(1)  # type: ignore[union-attr]
            suggestion = indent + "pass"
        return {"suggestion": suggestion}

    def list_results(
        self, kind: str | None = None, limit: int = 50,
    ) -> list[AIPAssistRequest]:
        items = list(self._results)
        if kind:
            items = [r for r in items if r.kind == kind]
        items = list(reversed(items))
        if limit > 0:
            items = items[:limit]
        return items


# ════════════════════ #108 RepoSettingsEngine ════════════════════

class RepoSettingsEngine:
    def __init__(self) -> None:
        self._settings: dict[str, RepoSettings] = {}
        self._lock = threading.Lock()

    def register(self, settings: RepoSettings) -> RepoSettings:
        if not settings.repo_id:
            raise AIPAssistError("MISSING_REPO", "repo_id 不能为空")
        # validation_rules 校验
        for rule in settings.validation_rules:
            kind = rule.get("kind", "")
            if kind not in _VALID_RULE_KINDS:
                raise AIPAssistError("INVALID_RULE_KIND", f"未知规则类型：{kind}")
        with self._lock:
            if len(self._settings) >= _MAX_SETTINGS:
                oldest_id = next(iter(self._settings))
                self._settings.pop(oldest_id, None)
            self._settings[settings.id] = settings
        return settings

    def get(self, settings_id: str) -> RepoSettings:
        s = self._settings.get(settings_id)
        if s is None:
            raise AIPAssistError("NOT_FOUND", f"仓库配置 {settings_id} 不存在")
        return s

    def get_by_repo(self, repo_id: str) -> RepoSettings | None:
        for s in self._settings.values():
            if s.repo_id == repo_id:
                return s
        return None

    def list(self, repo_id: str | None = None) -> list[RepoSettings]:
        items = list(self._settings.values())
        if repo_id:
            items = [s for s in items if s.repo_id == repo_id]
        return items

    def update(self, settings_id: str, updates: dict[str, Any]) -> RepoSettings:
        s = self.get(settings_id)
        for k, v in updates.items():
            if k in ("id", "created_at"):
                continue
            if k == "validation_rules" and isinstance(v, list):
                for rule in v:
                    kind = rule.get("kind", "") if isinstance(rule, dict) else ""
                    if kind not in _VALID_RULE_KINDS:
                        raise AIPAssistError("INVALID_RULE_KIND", f"未知规则类型：{kind}")
            if hasattr(s, k):
                setattr(s, k, v)
        s.updated_at = time.time()
        return s

    def delete(self, settings_id: str) -> bool:
        return self._settings.pop(settings_id, None) is not None

    def validate_label(self, settings_id: str, label: str) -> dict[str, Any]:
        s = self.get(settings_id)
        lv = s.label_validation or {}
        prefixes = lv.get("required_prefixes", []) or []
        # 前缀校验
        if prefixes:
            if not any(label.startswith(p) for p in prefixes):
                return {
                    "valid": False,
                    "reason": "missing required prefix",
                    "required_prefixes": prefixes,
                }
        # 颜色校验（简化：label 中 ":" 出现次数 >= 2 视为含颜色，如 bug:red:critical）
        if lv.get("color_required") is True:
            if label.count(":") < 2:
                return {
                    "valid": False,
                    "reason": "color required",
                }
        return {"valid": True, "reason": ""}

    def render_pr_template(
        self, settings_id: str, context: dict[str, Any],
    ) -> str:
        s = self.get(settings_id)
        rendered = s.pr_template
        # 简单占位符替换 {key}
        for k, v in context.items():
            rendered = rendered.replace("{" + k + "}", str(v))
        return rendered


# ════════════════════ #110 ProjectStructureEngine ════════════════════

class ProjectStructureEngine:
    def __init__(self) -> None:
        self._structures: dict[str, ProjectStructure] = {}
        self._lock = threading.Lock()

    def register(self, structure: ProjectStructure) -> ProjectStructure:
        if not structure.name:
            raise AIPAssistError("MISSING_NAME", "结构名称不能为空")
        # 校验 layers + components
        for layer in structure.layers:
            if layer not in _VALID_LAYERS:
                raise AIPAssistError("INVALID_LAYER", f"未知层：{layer}")
        for comp in structure.components:
            if comp.layer not in _VALID_LAYERS:
                raise AIPAssistError("INVALID_LAYER", f"未知层：{comp.layer}")
            if comp.type not in _VALID_COMPONENT_TYPES:
                raise AIPAssistError(
                    "INVALID_COMPONENT_TYPE", f"未知组件类型：{comp.type}",
                )
        with self._lock:
            if len(self._structures) >= _MAX_STRUCTURES:
                oldest_id = next(iter(self._structures))
                self._structures.pop(oldest_id, None)
            self._structures[structure.id] = structure
        return structure

    def get(self, struct_id: str) -> ProjectStructure:
        s = self._structures.get(struct_id)
        if s is None:
            raise AIPAssistError("NOT_FOUND", f"项目结构 {struct_id} 不存在")
        return s

    def list(self, name: str | None = None) -> list[ProjectStructure]:
        items = list(self._structures.values())
        if name:
            items = [s for s in items if s.name == name]
        return items

    def update(self, struct_id: str, updates: dict[str, Any]) -> ProjectStructure:
        s = self.get(struct_id)
        for k, v in updates.items():
            if k in ("id", "created_at"):
                continue
            if k == "layers" and isinstance(v, list):
                for layer in v:
                    if layer not in _VALID_LAYERS:
                        raise AIPAssistError("INVALID_LAYER", f"未知层：{layer}")
            if k == "components" and isinstance(v, list):
                for comp in v:
                    layer = comp.layer if hasattr(comp, "layer") else comp.get("layer", "")
                    ctype = comp.type if hasattr(comp, "type") else comp.get("type", "")
                    if layer not in _VALID_LAYERS:
                        raise AIPAssistError("INVALID_LAYER", f"未知层：{layer}")
                    if ctype not in _VALID_COMPONENT_TYPES:
                        raise AIPAssistError(
                            "INVALID_COMPONENT_TYPE", f"未知组件类型：{ctype}",
                        )
            if hasattr(s, k):
                setattr(s, k, v)
        return s

    def delete(self, struct_id: str) -> bool:
        return self._structures.pop(struct_id, None) is not None

    def render_template(self, struct_id: str) -> dict[str, Any]:
        s = self.get(struct_id)
        return {
            "name": s.name,
            "description": s.description,
            "layers": list(s.layers),
            "components": [c.model_dump() for c in s.components],
        }

    def validate_project(
        self, struct_id: str, project_components: list[dict[str, Any]],
    ) -> dict[str, Any]:
        s = self.get(struct_id)
        # 模板要求的 (layer, name) 集合
        required_keys = {
            (c.layer, c.name) for c in s.components if c.required
        }
        all_template_keys = {(c.layer, c.name) for c in s.components}
        # 项目实际拥有的 (layer, name) 集合
        project_keys = {
            (pc.get("layer", ""), pc.get("name", ""))
            for pc in project_components
            if isinstance(pc, dict)
        }
        missing = [
            {"layer": l, "name": n}
            for (l, n) in required_keys if (l, n) not in project_keys
        ]
        extra = [
            {"layer": l, "name": n}
            for (l, n) in project_keys
            if (l, n) not in all_template_keys and (l, n) not in required_keys
        ]
        return {
            "valid": len(missing) == 0,
            "missing": missing,
            "extra": extra,
        }


# ════════════════════ 单例 ════════════════════

_assist_engine: AIPAssistEngine | None = None
_settings_engine: RepoSettingsEngine | None = None
_structure_engine: ProjectStructureEngine | None = None
_singleton_lock = threading.Lock()


def get_assist_engine() -> AIPAssistEngine:
    global _assist_engine
    if _assist_engine is None:
        with _singleton_lock:
            if _assist_engine is None:
                _assist_engine = AIPAssistEngine()
    return _assist_engine


def get_settings_engine() -> RepoSettingsEngine:
    global _settings_engine
    if _settings_engine is None:
        with _singleton_lock:
            if _settings_engine is None:
                _settings_engine = RepoSettingsEngine()
    return _settings_engine


def get_structure_engine() -> ProjectStructureEngine:
    global _structure_engine
    if _structure_engine is None:
        with _singleton_lock:
            if _structure_engine is None:
                _structure_engine = ProjectStructureEngine()
    return _structure_engine
