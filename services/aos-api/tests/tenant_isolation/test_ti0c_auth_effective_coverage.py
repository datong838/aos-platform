"""app 级鉴权覆盖门禁：**不得新增「无有效鉴权」路由**。

存在理由（09-24「线上 vs HEAD」补洞时发现，P0）：
平台鉴权**没有全局中间件**（`middleware.py` 只做 trace/org/日志），
完全依赖每个路由自己声明 `require_principal`。而两种写法在 fastapi 0.141.1 下等价性**不成立**：

| 写法 | `dependant.dependencies` 是否含 `require_principal` | 无 token 实测 |
|---|---|---|
| `principal: Annotated[Principal, Depends(require_principal)]` | 是 | **401 AUTH_REQUIRED** |
| `_ = require_principal`（**裸函数当默认值**） | **否**（退化成名为 `_` 的 query 形参） | **200** |

⇒ 大量「作者明明写了 require_principal」的端点其实**从未鉴权**。
契约侧可见其指纹：这些操作会多出一个幽灵 query 形参 `_`
（快照 `v1.generated.json` 里恰好 659 个，与 AST 独立统计逐方法吻合）。

既有的 `test_ti0c_auth_fail_closed.py` 判据是**正确**的（它查的正是
`route.dependant.dependencies`），但它只挂了 **16 个模块的白名单**
（`PROTECTED_ROUTER_MODULES`）⇒ 白名单之外的新路由默认不受保护，属**失败开放**。

本文件的两条锁：
- `test_effective_auth_predicate_is_calibrated`：把上表两种写法做成**正/负对照**，
  锁住判据本身（防止有人把判据改宽以让门禁变绿）。
- `test_no_new_unauthenticated_routes`：当前无鉴权路由集必须是**冻结基线的子集**
  —— 只拦新增（失败即给出新增条目），不拦修复方向（减少是允许的，且应同步更新基线）。

⚠️ 基线**不是许可清单**，是**技术债清单**。修复后请用
`A0V_AUTH_BASELINE_UPDATE=1 ./.venv/bin/python -m pytest -q tests/tenant_isolation/test_ti0c_auth_effective_coverage.py`
重新生成，并在 D-waves 清单登记进度。
"""
from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Annotated, Iterator

from fastapi import APIRouter, Depends, FastAPI

from aos_api.auth import Principal, require_principal

BASELINE_PATH = Path(__file__).resolve().parent / "unauthenticated_routes_baseline.json"

# ⚠️ 正/负对照用的两个路由必须定义在**模块级**，且注解引用的名字必须在**模块全局**里。
# 本文件顶部有 `from __future__ import annotations` ⇒ 注解是字符串，FastAPI 用
# `func.__globals__` 解析类型提示；若 `Depends`/`require_principal` 只在函数内 import，
# 解析失败会让依赖**静默消失**（和本文件要防的裸默认值同一种病症）。
_CALIBRATION_ROUTER = APIRouter()


@_CALIBRATION_ROUTER.get("/good")
def _calibration_good(principal: Annotated[Principal, Depends(require_principal)]):  # noqa: ANN202
    return {"ok": principal.subject}


@_CALIBRATION_ROUTER.get("/bad")
def _calibration_bad(_=require_principal):  # noqa: ANN001, ANN202
    return {"ok": True}


def _walk_routes(routes) -> Iterator[object]:
    """扁平化真实路由表（fastapi 0.141.1 的 include_router 是惰性包装）。"""
    for route in routes:
        effective = getattr(route, "effective_candidates", None)
        if callable(effective):
            yield from _walk_routes(effective())
            continue
        if hasattr(route, "path") and hasattr(route, "dependant"):
            yield route
            continue
        nested = getattr(route, "routes", None)
        if nested:
            yield from _walk_routes(nested)


def _has_effective_auth(route) -> bool:
    """路由的依赖树里是否存在真正被注入的 `require_principal`。"""

    def rec(dep) -> bool:
        if getattr(dep, "call", None) is require_principal:
            return True
        return any(rec(sub) for sub in dep.dependencies)

    return any(rec(dep) for dep in route.dependant.dependencies)


def _unauthenticated_entries() -> list[str]:
    from aos_api.main import create_app

    app = create_app()
    out = []
    for route in _walk_routes(app.router.routes):
        if _has_effective_auth(route):
            continue
        for method in sorted(getattr(route, "methods", set()) or set()):
            if method in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                out.append(f"{method} {route.path}")
    return sorted(set(out))


def test_effective_auth_predicate_is_calibrated() -> None:
    """正/负对照：判据必须认 `Depends(...)`、必须拒裸函数默认值。"""
    app = FastAPI()
    app.include_router(_CALIBRATION_ROUTER)
    verdicts = {
        route.path: _has_effective_auth(route) for route in _walk_routes(app.routes)
    }
    assert verdicts["/good"] is True, "`Depends(...)` 形态必须被判为已鉴权"
    assert verdicts["/bad"] is False, "裸 `_ = require_principal` 是**未鉴权**，判据不得放水"


def _new_vs_baseline(entries: list[str], known: set[str]) -> list[str]:
    """只拦新增：减少（修复）方向允许通过。"""
    return sorted(set(entries) - known)


def test_baseline_diff_flags_additions_and_allows_removals() -> None:
    known = {"GET /a", "POST /b", "DELETE /c"}
    assert _new_vs_baseline(["GET /a", "POST /b"], known) == []
    assert _new_vs_baseline(["GET /a", "POST /b", "DELETE /c", "PUT /d"], known) == [
        "PUT /d"
    ]


def test_no_new_unauthenticated_routes() -> None:
    entries = _unauthenticated_entries()
    by_method = Counter(e.split(" ", 1)[0] for e in entries)
    if os.getenv("A0V_AUTH_BASELINE_UPDATE") == "1":
        BASELINE_PATH.write_text(
            json.dumps(
                {
                    "note": "无有效鉴权路由冻结基线（技术债清单，非许可清单）",
                    "count": len(entries),
                    "byMethod": dict(sorted(by_method.items())),
                    "entries": entries,
                },
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )
        return

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    new = _new_vs_baseline(entries, set(baseline["entries"]))
    assert not new, (
        f"新增了 {len(new)} 条无有效鉴权路由（基线 {baseline['count']} 条）。"
        "修法：用 `Annotated[Principal, Depends(require_principal)]` 声明依赖"
        "（裸函数当默认值**不会**被注入，参照本文件正/负对照）。\n"
        + "\n".join(f"  + {e}" for e in new[:40])
    )
