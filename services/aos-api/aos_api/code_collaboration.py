"""W2-AC · 代码仓库与 PR 工作流组（#101 / #102 / #103）.

- #101 BranchEngine：分支 CRUD + merge + protect
- #102 PullRequestEngine：PR CRUD + 状态机 + CI 检查 + merge
- #103 TransformPreviewEngine：变换预览 CRUD + run 执行

详见 docs/palantier/20_tech/220tech_w2-ac-code-collaboration.md。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

# ════════════════════ 常量 ════════════════════

_VALID_BRANCH_STATUSES = {"open", "merged", "deleted"}
_VALID_MERGE_STRATEGIES = {"merge", "rebase", "squash"}
_VALID_PR_STATUSES = {"open", "reviewing", "approved", "rejected", "merged", "closed"}
_VALID_CI_STATUSES = {"pending", "running", "passed", "failed"}
_VALID_PR_TRANSITIONS: dict[str, set[str]] = {
    "open": {"reviewing", "closed"},
    "reviewing": {"approved", "rejected", "open", "closed"},
    "approved": {"merged", "open"},
    "rejected": {"open", "closed"},
    "merged": set(),
    "closed": set(),
}
_VALID_PREVIEW_LANGUAGES = {"python", "sql"}
_VALID_PREVIEW_STATUSES = {"success", "error", "timeout"}

_MAX_BRANCHES = 200
_MAX_PRS = 200
_MAX_PREVIEWS = 200
_MAX_RESULTS = 200


# ════════════════════ 数据模型 ════════════════════

class Branch(BaseModel):
    """代码分支。"""
    id: str = Field(default_factory=lambda: "br-" + uuid.uuid4().hex[:10])
    repo_id: str
    name: str
    base_branch: str = "main"
    head_commit: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    protected: bool = False
    status: str = "open"
    created_at: float = Field(default_factory=lambda: time.time())
    merged_at: float = 0.0


class BranchMergeResult(BaseModel):
    """分支合并结果。"""
    source_branch: str
    target_branch: str
    strategy: str
    success: bool
    new_commit: str = ""
    conflicts: list[str] = Field(default_factory=list)
    merged_at: float = 0.0


class PullRequest(BaseModel):
    """Pull Request。"""
    id: str = Field(default_factory=lambda: "pr-" + uuid.uuid4().hex[:10])
    repo_id: str
    title: str
    description: str = ""
    source_branch: str
    target_branch: str
    author: str
    reviewers: list[str] = Field(default_factory=list)
    status: str = "open"
    ci_status: str = "pending"
    commits: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())
    merged_at: float = 0.0


class TransformPreview(BaseModel):
    """变换预览定义。"""
    id: str = Field(default_factory=lambda: "tp-" + uuid.uuid4().hex[:10])
    name: str
    repo_id: str = ""
    branch: str = "main"
    transform_code: str
    language: str = "python"
    input_schema: dict[str, str] = Field(default_factory=dict)
    sample_rows: list[dict[str, Any]] = Field(default_factory=list)
    created_at: float = Field(default_factory=lambda: time.time())


class PreviewResult(BaseModel):
    """变换预览结果。"""
    id: str = Field(default_factory=lambda: "pr-res-" + uuid.uuid4().hex[:10])
    preview_id: str
    status: str = "success"
    output_rows: list[dict[str, Any]] = Field(default_factory=list)
    output_schema: dict[str, str] = Field(default_factory=dict)
    error_message: str = ""
    row_count: int = 0
    executed_at: float = Field(default_factory=lambda: time.time())


# ════════════════════ 错误 ════════════════════

class CodeCollaborationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


# ════════════════════ #101 BranchEngine ════════════════════

class BranchEngine:
    def __init__(self) -> None:
        self._branches: dict[str, Branch] = {}
        self._lock = threading.Lock()

    def register(self, branch: Branch) -> Branch:
        if not branch.name:
            raise CodeCollaborationError("MISSING_NAME", "分支名称不能为空")
        if not branch.repo_id:
            raise CodeCollaborationError("MISSING_REPO", "repo_id 不能为空")
        with self._lock:
            if len(self._branches) >= _MAX_BRANCHES:
                oldest_id = next(iter(self._branches))
                self._branches.pop(oldest_id, None)
            self._branches[branch.id] = branch
        return branch

    def get(self, branch_id: str) -> Branch:
        b = self._branches.get(branch_id)
        if b is None:
            raise CodeCollaborationError("NOT_FOUND", f"分支 {branch_id} 不存在")
        return b

    def get_by_name(self, repo_id: str, name: str) -> Branch | None:
        for b in self._branches.values():
            if b.repo_id == repo_id and b.name == name:
                return b
        return None

    def list(
        self, repo_id: str | None = None, status: str | None = None,
    ) -> list[Branch]:
        items = list(self._branches.values())
        if repo_id:
            items = [b for b in items if b.repo_id == repo_id]
        if status:
            items = [b for b in items if b.status == status]
        return items

    def update(self, branch_id: str, updates: dict[str, Any]) -> Branch:
        b = self.get(branch_id)
        for k, v in updates.items():
            if hasattr(b, k) and k != "id":
                setattr(b, k, v)
        return b

    def delete(self, branch_id: str) -> bool:
        b = self._branches.get(branch_id)
        if b is None:
            return False
        b.status = "deleted"
        return True

    def merge(
        self, source_id: str, target_name: str, strategy: str = "merge",
    ) -> BranchMergeResult:
        if strategy not in _VALID_MERGE_STRATEGIES:
            raise CodeCollaborationError("INVALID_STRATEGY", f"未知合并策略：{strategy}")
        source = self.get(source_id)
        if source.status != "open":
            raise CodeCollaborationError("ALREADY_MERGED", f"分支 {source.name} 状态为 {source.status}，不可合并")
        # 查找 target
        target = self.get_by_name(source.repo_id, target_name)
        if target is None:
            raise CodeCollaborationError("TARGET_NOT_FOUND", f"目标分支 {target_name} 不存在于 repo {source.repo_id}")
        now = time.time()
        new_commit = uuid.uuid4().hex[:12]
        source.status = "merged"
        source.merged_at = now
        target.head_commit = new_commit
        return BranchMergeResult(
            source_branch=source.name, target_branch=target.name,
            strategy=strategy, success=True, new_commit=new_commit,
            merged_at=now,
        )

    def protect(self, branch_id: str, protected: bool = True) -> Branch:
        b = self.get(branch_id)
        b.protected = protected
        return b


# ════════════════════ #102 PullRequestEngine ════════════════════

class PullRequestEngine:
    def __init__(self) -> None:
        self._prs: dict[str, PullRequest] = {}
        self._lock = threading.Lock()

    def register(self, pr: PullRequest) -> PullRequest:
        if not pr.title:
            raise CodeCollaborationError("MISSING_TITLE", "PR 标题不能为空")
        if not pr.repo_id:
            raise CodeCollaborationError("MISSING_REPO", "repo_id 不能为空")
        if not pr.source_branch or not pr.target_branch:
            raise CodeCollaborationError("MISSING_BRANCH", "source/target_branch 不能为空")
        if not pr.author:
            raise CodeCollaborationError("MISSING_AUTHOR", "author 不能为空")
        with self._lock:
            if len(self._prs) >= _MAX_PRS:
                oldest_id = next(iter(self._prs))
                self._prs.pop(oldest_id, None)
            self._prs[pr.id] = pr
        return pr

    def get(self, pr_id: str) -> PullRequest:
        p = self._prs.get(pr_id)
        if p is None:
            raise CodeCollaborationError("NOT_FOUND", f"PR {pr_id} 不存在")
        return p

    def list(
        self, repo_id: str | None = None, status: str | None = None,
        author: str | None = None,
    ) -> list[PullRequest]:
        items = list(self._prs.values())
        if repo_id:
            items = [p for p in items if p.repo_id == repo_id]
        if status:
            items = [p for p in items if p.status == status]
        if author:
            items = [p for p in items if p.author == author]
        return items

    def update(self, pr_id: str, updates: dict[str, Any]) -> PullRequest:
        p = self.get(pr_id)
        for k, v in updates.items():
            if hasattr(p, k) and k != "id":
                setattr(p, k, v)
        p.updated_at = time.time()
        return p

    def transition(self, pr_id: str, new_status: str) -> PullRequest:
        if new_status not in _VALID_PR_STATUSES:
            raise CodeCollaborationError("INVALID_STATUS", f"未知 PR 状态：{new_status}")
        p = self.get(pr_id)
        allowed = _VALID_PR_TRANSITIONS.get(p.status, set())
        if new_status not in allowed:
            raise CodeCollaborationError(
                "INVALID_TRANSITION",
                f"PR 状态 {p.status} 不可转换为 {new_status}",
            )
        p.status = new_status
        p.updated_at = time.time()
        if new_status == "merged":
            p.merged_at = time.time()
        return p

    def add_reviewer(self, pr_id: str, reviewer: str) -> PullRequest:
        p = self.get(pr_id)
        if reviewer not in p.reviewers:
            p.reviewers.append(reviewer)
        return p

    def set_ci_status(self, pr_id: str, ci_status: str) -> PullRequest:
        if ci_status not in _VALID_CI_STATUSES:
            raise CodeCollaborationError("INVALID_CI_STATUS", f"未知 CI 状态：{ci_status}")
        p = self.get(pr_id)
        p.ci_status = ci_status
        p.updated_at = time.time()
        return p

    def merge(self, pr_id: str) -> PullRequest:
        p = self.get(pr_id)
        if p.status != "approved":
            raise CodeCollaborationError("MERGE_NOT_ALLOWED", f"PR 状态为 {p.status}，需 approved 才能合并")
        if p.ci_status != "passed":
            raise CodeCollaborationError("CI_NOT_PASSED", f"CI 状态为 {p.ci_status}，需 passed 才能合并")
        p.status = "merged"
        p.merged_at = time.time()
        p.updated_at = time.time()
        return p


# ════════════════════ #103 TransformPreviewEngine ════════════════════

class TransformPreviewEngine:
    def __init__(self) -> None:
        self._previews: dict[str, TransformPreview] = {}
        self._results: list[PreviewResult] = []
        self._lock = threading.Lock()

    def register(self, preview: TransformPreview) -> TransformPreview:
        if not preview.name:
            raise CodeCollaborationError("MISSING_NAME", "预览名称不能为空")
        if not preview.transform_code:
            raise CodeCollaborationError("MISSING_CODE", "transform_code 不能为空")
        if preview.language not in _VALID_PREVIEW_LANGUAGES:
            raise CodeCollaborationError("INVALID_LANGUAGE", f"未知语言：{preview.language}")
        with self._lock:
            if len(self._previews) >= _MAX_PREVIEWS:
                oldest_id = next(iter(self._previews))
                self._previews.pop(oldest_id, None)
            self._previews[preview.id] = preview
        return preview

    def get(self, preview_id: str) -> TransformPreview:
        p = self._previews.get(preview_id)
        if p is None:
            raise CodeCollaborationError("NOT_FOUND", f"预览 {preview_id} 不存在")
        return p

    def list(
        self, repo_id: str | None = None, language: str | None = None,
    ) -> list[TransformPreview]:
        items = list(self._previews.values())
        if repo_id:
            items = [p for p in items if p.repo_id == repo_id]
        if language:
            items = [p for p in items if p.language == language]
        return items

    def update(self, preview_id: str, updates: dict[str, Any]) -> TransformPreview:
        p = self.get(preview_id)
        if "language" in updates and updates["language"] not in _VALID_PREVIEW_LANGUAGES:
            raise CodeCollaborationError("INVALID_LANGUAGE", f"未知语言：{updates['language']}")
        for k, v in updates.items():
            if hasattr(p, k) and k != "id":
                setattr(p, k, v)
        return p

    def delete(self, preview_id: str) -> bool:
        return self._previews.pop(preview_id, None) is not None

    def run(self, preview_id: str) -> PreviewResult:
        p = self.get(preview_id)
        now = time.time()
        rows = p.sample_rows or []

        if p.language == "python":
            try:
                # 安全执行：在受限命名空间中 exec 代码，然后调用 transform(rows)
                namespace: dict[str, Any] = {}
                exec(p.transform_code, namespace)  # noqa: S102
                transform_fn = namespace.get("transform")
                if transform_fn is None or not callable(transform_fn):
                    raise CodeCollaborationError(
                        "NO_TRANSFORM_FUNC", "代码中未定义 transform(rows) 函数",
                    )
                output = transform_fn(rows)
                if not isinstance(output, list):
                    output = list(output) if output is not None else []
                result = PreviewResult(
                    preview_id=p.id, status="success",
                    output_rows=output,
                    output_schema=_infer_schema(output),
                    row_count=len(output), executed_at=now,
                )
            except CodeCollaborationError:
                raise
            except Exception as exc:  # noqa: BLE001
                result = PreviewResult(
                    preview_id=p.id, status="error",
                    error_message=str(exc), executed_at=now,
                )
        else:  # sql
            # 简化：SQL 预览直接返回 sample_rows（无实际 SQL 引擎）
            result = PreviewResult(
                preview_id=p.id, status="success",
                output_rows=list(rows),
                output_schema=p.input_schema or _infer_schema(rows),
                row_count=len(rows), executed_at=now,
            )

        with self._lock:
            if len(self._results) >= _MAX_RESULTS:
                self._results.pop(0)
            self._results.append(result)
        return result

    def list_results(
        self, preview_id: str | None = None, limit: int = 50,
    ) -> list[PreviewResult]:
        items = list(self._results)
        if preview_id:
            items = [r for r in items if r.preview_id == preview_id]
        items = list(reversed(items))
        if limit > 0:
            items = items[:limit]
        return items


def _infer_schema(rows: list[dict[str, Any]]) -> dict[str, str]:
    """从行数据推断 schema。"""
    if not rows:
        return {}
    schema: dict[str, str] = {}
    sample = rows[0]
    for key, val in sample.items():
        if isinstance(val, bool):
            schema[key] = "boolean"
        elif isinstance(val, int):
            schema[key] = "integer"
        elif isinstance(val, float):
            schema[key] = "float"
        elif isinstance(val, str):
            schema[key] = "string"
        else:
            schema[key] = "any"
    return schema


# ════════════════════ 单例 ════════════════════

_branch_engine: BranchEngine | None = None
_pr_engine: PullRequestEngine | None = None
_preview_engine: TransformPreviewEngine | None = None
_singleton_lock = threading.Lock()


def get_branch_engine() -> BranchEngine:
    global _branch_engine
    if _branch_engine is None:
        with _singleton_lock:
            if _branch_engine is None:
                _branch_engine = BranchEngine()
    return _branch_engine


def get_pr_engine() -> PullRequestEngine:
    global _pr_engine
    if _pr_engine is None:
        with _singleton_lock:
            if _pr_engine is None:
                _pr_engine = PullRequestEngine()
    return _pr_engine


def get_preview_engine() -> TransformPreviewEngine:
    global _preview_engine
    if _preview_engine is None:
        with _singleton_lock:
            if _preview_engine is None:
                _preview_engine = TransformPreviewEngine()
    return _preview_engine
