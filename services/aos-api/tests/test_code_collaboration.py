"""W2-AC · 代码仓库与 PR 工作流组测试（#101 / #102 / #103）.

覆盖 BranchEngine / PullRequestEngine / TransformPreviewEngine 三引擎。
对齐 docs/palantier/20_tech/220tech_w2-ac-code-collaboration.md §6 测试计划。
"""
from __future__ import annotations

import pytest

from aos_api.code_collaboration import (
    Branch,
    BranchEngine,
    CodeCollaborationError,
    PullRequest,
    PullRequestEngine,
    PreviewResult,
    TransformPreview,
    TransformPreviewEngine,
    get_branch_engine,
    get_pr_engine,
    get_preview_engine,
    _MAX_RESULTS,
)


# ════════════════════ BranchEngine ════════════════════

class TestBranch:
    def setup_method(self) -> None:
        self.eng = BranchEngine()

    def _mk(self, **kw: object) -> Branch:
        defaults: dict[str, object] = {"repo_id": "repo-1", "name": "feature-1"}
        defaults.update(kw)
        return Branch(**defaults)

    def test_register_returns_with_id(self) -> None:
        b = self.eng.register(self._mk())
        assert b.id.startswith("br-")
        assert b.status == "open"

    def test_register_missing_name(self) -> None:
        with pytest.raises(CodeCollaborationError) as exc:
            self.eng.register(self._mk(name=""))
        assert exc.value.code == "MISSING_NAME"

    def test_get_not_found(self) -> None:
        with pytest.raises(CodeCollaborationError) as exc:
            self.eng.get("not-exist")
        assert exc.value.code == "NOT_FOUND"

    def test_get_by_name(self) -> None:
        b = self.eng.register(self._mk(repo_id="repo-1", name="dev"))
        found = self.eng.get_by_name("repo-1", "dev")
        assert found is not None
        assert found.id == b.id
        assert self.eng.get_by_name("repo-1", "missing") is None

    def test_list_default(self) -> None:
        self.eng.register(self._mk(name="b1"))
        self.eng.register(self._mk(name="b2"))
        assert len(self.eng.list()) == 2

    def test_list_filter_by_repo_id(self) -> None:
        self.eng.register(self._mk(repo_id="repo-1", name="b1"))
        self.eng.register(self._mk(repo_id="repo-2", name="b2"))
        items = self.eng.list(repo_id="repo-1")
        assert len(items) == 1
        assert items[0].repo_id == "repo-1"

    def test_list_filter_by_status(self) -> None:
        b1 = self.eng.register(self._mk(name="b1"))
        self.eng.register(self._mk(name="b2"))
        b1.status = "merged"
        items = self.eng.list(status="merged")
        assert len(items) == 1
        assert items[0].name == "b1"

    def test_update(self) -> None:
        b = self.eng.register(self._mk(name="old"))
        updated = self.eng.update(b.id, {"name": "new", "protected": True})
        assert updated.name == "new"
        assert updated.protected is True

    def test_delete_marks_status(self) -> None:
        b = self.eng.register(self._mk(name="b1"))
        assert self.eng.delete(b.id) is True
        # 删除是把状态置为 deleted，仍可通过 get 读取
        assert self.eng.get(b.id).status == "deleted"
        assert self.eng.delete("missing") is False

    def test_merge_success(self) -> None:
        # 同时注册 source 和 target
        self.eng.register(self._mk(repo_id="repo-1", name="main"))
        src = self.eng.register(self._mk(repo_id="repo-1", name="feature"))
        result = self.eng.merge(src.id, "main")
        assert result.success is True
        assert result.strategy == "merge"
        assert self.eng.get(src.id).status == "merged"

    def test_merge_already_merged(self) -> None:
        self.eng.register(self._mk(repo_id="repo-1", name="main"))
        src = self.eng.register(self._mk(repo_id="repo-1", name="feature"))
        self.eng.merge(src.id, "main")
        with pytest.raises(CodeCollaborationError) as exc:
            self.eng.merge(src.id, "main")
        assert exc.value.code == "ALREADY_MERGED"

    def test_merge_target_not_found(self) -> None:
        src = self.eng.register(self._mk(repo_id="repo-1", name="feature"))
        with pytest.raises(CodeCollaborationError) as exc:
            self.eng.merge(src.id, "main")
        assert exc.value.code == "TARGET_NOT_FOUND"

    def test_protect(self) -> None:
        b = self.eng.register(self._mk(name="b1"))
        assert b.protected is False
        out = self.eng.protect(b.id, True)
        assert out.protected is True
        out2 = self.eng.protect(b.id, False)
        assert out2.protected is False

    def test_merge_with_rebase_strategy(self) -> None:
        self.eng.register(self._mk(repo_id="repo-1", name="main"))
        src = self.eng.register(self._mk(repo_id="repo-1", name="feature"))
        result = self.eng.merge(src.id, "main", strategy="rebase")
        assert result.strategy == "rebase"
        assert result.success is True


# ════════════════════ PullRequestEngine ════════════════════

class TestPullRequest:
    def setup_method(self) -> None:
        self.eng = PullRequestEngine()

    def _mk(self, **kw: object) -> PullRequest:
        defaults: dict[str, object] = {
            "repo_id": "repo-1",
            "title": "Add feature",
            "source_branch": "feature",
            "target_branch": "main",
            "author": "alice",
        }
        defaults.update(kw)
        return PullRequest(**defaults)

    def test_register_returns_with_id(self) -> None:
        p = self.eng.register(self._mk())
        assert p.id.startswith("pr-")
        assert p.status == "open"

    def test_register_missing_title(self) -> None:
        with pytest.raises(CodeCollaborationError) as exc:
            self.eng.register(self._mk(title=""))
        assert exc.value.code == "MISSING_TITLE"

    def test_get_not_found(self) -> None:
        with pytest.raises(CodeCollaborationError) as exc:
            self.eng.get("missing")
        assert exc.value.code == "NOT_FOUND"

    def test_list_default(self) -> None:
        self.eng.register(self._mk(title="p1"))
        self.eng.register(self._mk(title="p2"))
        assert len(self.eng.list()) == 2

    def test_list_filter_by_repo_id(self) -> None:
        self.eng.register(self._mk(repo_id="repo-1", title="p1"))
        self.eng.register(self._mk(repo_id="repo-2", title="p2"))
        items = self.eng.list(repo_id="repo-1")
        assert len(items) == 1
        assert items[0].repo_id == "repo-1"

    def test_list_filter_by_status(self) -> None:
        p1 = self.eng.register(self._mk(title="p1"))
        self.eng.register(self._mk(title="p2"))
        self.eng.transition(p1.id, "reviewing")
        items = self.eng.list(status="reviewing")
        assert len(items) == 1
        assert items[0].id == p1.id

    def test_list_filter_by_author(self) -> None:
        self.eng.register(self._mk(author="alice", title="p1"))
        self.eng.register(self._mk(author="bob", title="p2"))
        items = self.eng.list(author="alice")
        assert len(items) == 1
        assert items[0].author == "alice"

    def test_update(self) -> None:
        p = self.eng.register(self._mk(title="old"))
        out = self.eng.update(p.id, {"title": "new", "description": "updated"})
        assert out.title == "new"
        assert out.description == "updated"

    def test_transition_open_to_reviewing(self) -> None:
        p = self.eng.register(self._mk())
        out = self.eng.transition(p.id, "reviewing")
        assert out.status == "reviewing"

    def test_transition_invalid(self) -> None:
        p = self.eng.register(self._mk())
        # open → approved 是非法转换
        with pytest.raises(CodeCollaborationError) as exc:
            self.eng.transition(p.id, "approved")
        assert exc.value.code == "INVALID_TRANSITION"

    def test_add_reviewer(self) -> None:
        p = self.eng.register(self._mk())
        out = self.eng.add_reviewer(p.id, "bob")
        assert "bob" in out.reviewers
        # 重复添加幂等
        out2 = self.eng.add_reviewer(p.id, "bob")
        assert out2.reviewers.count("bob") == 1

    def test_set_ci_status(self) -> None:
        p = self.eng.register(self._mk())
        out = self.eng.set_ci_status(p.id, "passed")
        assert out.ci_status == "passed"
        with pytest.raises(CodeCollaborationError) as exc:
            self.eng.set_ci_status(p.id, "unknown")
        assert exc.value.code == "INVALID_CI_STATUS"

    def test_merge_success(self) -> None:
        p = self.eng.register(self._mk())
        self.eng.transition(p.id, "reviewing")
        self.eng.transition(p.id, "approved")
        self.eng.set_ci_status(p.id, "passed")
        out = self.eng.merge(p.id)
        assert out.status == "merged"
        assert out.merged_at > 0

    def test_merge_not_approved(self) -> None:
        p = self.eng.register(self._mk())
        # 仅 reviewing，未 approved
        self.eng.transition(p.id, "reviewing")
        self.eng.set_ci_status(p.id, "passed")
        with pytest.raises(CodeCollaborationError) as exc:
            self.eng.merge(p.id)
        assert exc.value.code == "MERGE_NOT_ALLOWED"

    def test_merge_ci_failed(self) -> None:
        p = self.eng.register(self._mk())
        self.eng.transition(p.id, "reviewing")
        self.eng.transition(p.id, "approved")
        # ci_status=failed
        self.eng.set_ci_status(p.id, "failed")
        with pytest.raises(CodeCollaborationError) as exc:
            self.eng.merge(p.id)
        assert exc.value.code == "CI_NOT_PASSED"


# ════════════════════ TransformPreviewEngine ════════════════════

class TestTransformPreview:
    def setup_method(self) -> None:
        self.eng = TransformPreviewEngine()

    def _mk(self, **kw: object) -> TransformPreview:
        defaults: dict[str, object] = {
            "name": "preview-1",
            "transform_code": "def transform(rows):\n    return rows\n",
            "language": "python",
            "sample_rows": [{"id": 1, "name": "alice"}],
        }
        defaults.update(kw)
        return TransformPreview(**defaults)

    def test_register_returns_with_id(self) -> None:
        p = self.eng.register(self._mk())
        assert p.id.startswith("tp-")

    def test_register_missing_name(self) -> None:
        with pytest.raises(CodeCollaborationError) as exc:
            self.eng.register(self._mk(name=""))
        assert exc.value.code == "MISSING_NAME"

    def test_register_invalid_language(self) -> None:
        with pytest.raises(CodeCollaborationError) as exc:
            self.eng.register(self._mk(language="rust"))
        assert exc.value.code == "INVALID_LANGUAGE"

    def test_get_not_found(self) -> None:
        with pytest.raises(CodeCollaborationError) as exc:
            self.eng.get("missing")
        assert exc.value.code == "NOT_FOUND"

    def test_list_default(self) -> None:
        self.eng.register(self._mk(name="p1"))
        self.eng.register(self._mk(name="p2"))
        assert len(self.eng.list()) == 2

    def test_list_filter_by_language(self) -> None:
        self.eng.register(self._mk(name="p1", language="python"))
        self.eng.register(self._mk(name="p2", language="sql", transform_code="SELECT 1"))
        items = self.eng.list(language="sql")
        assert len(items) == 1
        assert items[0].language == "sql"

    def test_update(self) -> None:
        p = self.eng.register(self._mk(name="old"))
        out = self.eng.update(p.id, {"name": "new", "branch": "dev"})
        assert out.name == "new"
        assert out.branch == "dev"

    def test_delete(self) -> None:
        p = self.eng.register(self._mk())
        assert self.eng.delete(p.id) is True
        assert self.eng.delete(p.id) is False

    def test_run_python_success(self) -> None:
        code = "def transform(rows):\n    return [{'out': r['id'] * 2} for r in rows]\n"
        p = self.eng.register(self._mk(transform_code=code))
        r = self.eng.run(p.id)
        assert r.status == "success"
        assert r.row_count == 1
        assert r.output_rows == [{"out": 2}]
        assert r.output_schema == {"out": "integer"}

    def test_run_python_error(self) -> None:
        code = "def transform(rows):\n    raise ValueError('boom')\n"
        p = self.eng.register(self._mk(transform_code=code))
        r = self.eng.run(p.id)
        assert r.status == "error"
        assert "boom" in r.error_message

    def test_run_sql_passthrough(self) -> None:
        p = self.eng.register(self._mk(
            language="sql", transform_code="SELECT 1",
            sample_rows=[{"a": 1}],
        ))
        r = self.eng.run(p.id)
        assert r.status == "success"
        assert r.output_rows == [{"a": 1}]
        assert r.row_count == 1

    def test_list_results(self) -> None:
        p = self.eng.register(self._mk())
        self.eng.run(p.id)
        self.eng.run(p.id)
        items = self.eng.list_results(preview_id=p.id)
        assert len(items) == 2
        # 默认按时间倒序
        assert all(r.preview_id == p.id for r in items)

    def test_results_cap_eviction(self) -> None:
        # 连续运行 _MAX_RESULTS + 10 次，应淘汰旧记录
        p = self.eng.register(self._mk())
        for _ in range(_MAX_RESULTS + 10):
            self.eng.run(p.id)
        assert len(self.eng._results) == _MAX_RESULTS


# ════════════════════ 单例 ════════════════════

class TestSingletons:
    def test_branch_engine_singleton(self) -> None:
        a = get_branch_engine()
        b = get_branch_engine()
        assert a is b

    def test_pr_engine_singleton(self) -> None:
        a = get_pr_engine()
        b = get_pr_engine()
        assert a is b

    def test_preview_engine_singleton(self) -> None:
        a = get_preview_engine()
        b = get_preview_engine()
        assert a is b
