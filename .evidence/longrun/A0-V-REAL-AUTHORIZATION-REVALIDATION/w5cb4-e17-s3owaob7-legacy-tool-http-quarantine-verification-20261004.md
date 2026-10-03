# E17-s3o-w-ao-b7｜旧内存 Tool HTTP 入口禁入验证

## 上位与现场

先读 W2-B 220 §2.2、231/BIND-1、当前签名来源 b5/Tool RED b6，以及原 `tool_registry.py`/router/生成式 domain manifest。当前原 API `/openapi.json` 对 register/invoke/delete 显示 `security=[]`，未认证 `GET /v1/tools` 返回200/空列表；未发任何 POST/DELETE。旧 ToolRegistry 是进程内编程接口，既无 signed ToolDefinition、安装 epoch、发行 Receipt，也没有公共受限身份。当前四签名 bundle 不含正式 ToolDefinition。

## RED、实现和相邻回归

| 门 | 结果 |
| --- | --- |
| RED | 首版测试直接枚举 `app.routes` 得到假通过：主 app 用 `_IncludedRouter` 懒装载，不能据此判公开路径。改为 `app.openapi()["paths"]` 后同目标 `1 failed`/exit1，精确显示旧路由仍公开。 |
| 最小实现 | `domain_aggregates.py` 由 551 项 manifest 生成，直接改会产生大范围重排；只移除 `routers/tool_registry.py` 九条公开路由装饰器。保留模块函数、内存 ToolRegistry、Logic `use_tool` Python 接口；不修改 ToolBinding DTO/DB/Receipt，不伪造正式来源。 |
| 回归 | `AOS_DOTENV_DISABLED=1 PYTHONPATH=../..:. uv run pytest -q tests/aip/test_e17_s3owaob7_legacy_tool_http_routes.py tests/test_tool_registry.py tests/test_not_found_status_mapping.py`（API目录）→40 passed/8既有 warnings，exit0；随后把路由断言补全到九条再跑目标1 passed/exit0。`python3 scripts/generate_domain_aggregates.py --check` →551项匹配，exit0；`py_compile` 与 `git diff --check` exit0。 |

## 边界

本波仅关闭旧 HTTP 暴露，不算 ToolBinding 正式发行或经营首链。当前真实库未写，Host/worker/Provider关；当前运行 API 仍是旧代码，需完成原权威卷 PG→API→Web 质量重启、OpenAPI 路由读回及页面禁入复验后才可称 live 生效。正式 signed ToolDefinition、专用 issuer/同事务 Receipt/普通 runtime 收权仍 pending。
