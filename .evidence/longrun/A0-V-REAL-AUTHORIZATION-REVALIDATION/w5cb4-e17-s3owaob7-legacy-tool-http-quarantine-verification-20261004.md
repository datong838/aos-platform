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

本波仅关闭旧 HTTP 暴露，不算 ToolBinding 正式发行或经营首链。当前真实库未写，Host/worker/Provider关；正式 signed ToolDefinition、专用 issuer/同事务 Receipt/普通 runtime 收权仍 pending。

## 最新代码与原卷运行读回（2026-10-04 02:29–02:36 CST）

- 启动前独立全备 `aos-recovery/.aos-current-backup-20261004-s3owaob3/current-full.dump` SHA256 `28b356f3e7c8eb3ecf7c994e205d04ee4c2ad6f575644d3d9a8044e74c6db6f1`，原签名安装预检 exit0；代码 `m1@4bbb7d77`，库与代码迁移同为 `a0v_135`。
- 原 launchd Web/API 依次 bootout exit0；`docker --context colima-aos-extension restart aos-a0v-recovery-pg` exit0，再 bootstrap API/Web 各 exit0。容器 `running`、启动时刻 `2026-10-03T18:29:49.972067405Z`，挂载名 `aos-a0v-recovery-pg-data:/var/lib/postgresql/data`。新 API PID55664、Web PID55690；18435/8080/8434 LISTEN，18181无 LISTEN。
- 原库 `BEGIN READ ONLY` 查询 alembic=`a0v_135`、正式 Reader/Capability issuer 角色数 `0/0`，exit0；源库未做 DDL/业务写。签名安装预检复跑 exit0，Installation approved、publishedVersions4、runtimeBindings0。
- API `/v1/health`、`/v1/ready` 各200，未认证 `GET /v1/tools` 404；运行时 OpenAPI 的 `/v1/tools*`、`/v1/capabilities*` 路径空数组；八个 `/workshop/{cockpit,content-campaign,operations,creator-growth,media-studio,analyst,price-governance,customer}` 各200。以上服务端只读 HTTP 脚本 exit0。先用系统 Python3.9、5秒超时取巨大 OpenAPI 时 `socket.timeout` exit1；改用 API venv Python3.11、30秒超时复验 exit0，不将超时算功能故障。
- In-app browser 通过 CUA 对已打开的 `/aip/skill-publish` 重载并截图读屏：org-org/dev-project、37已评测/发布0，缺正式 Skill 发布决定、当前发布 Logic、可用模型路由策略，发布按钮禁用，无可见电商业务入口。截图已在本轮 UI 工具输出展示；该工具未提供本地写文件通道，故未声称仓库内有截图文件。未点发布或任何业务按钮。
