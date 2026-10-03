# W5CB4 E17-s3o-q｜ToolBinding 原写路径版本门验证

日期 2026-10-03。依同名计划、231/231-9、128 W-L20，只在自动销毁 PG135 执行。当前真实库未写。

| 门 | 证据 |
|---|---|
| RED | 新 `test_e17_s3oq_tool_binding_issuance_pg.py` 在旧原 Store 下 exit1：同 version1 改 `tool_id` 及 version2 后写回 version1 均未抛错，2 failed/1 passed。原 `ON CONFLICT DO UPDATE` 无版本条件，验证了发行数据可覆写。 |
| 最小修复 | `aip_assignee_resolution_store.py` 的原 INSERT 冲突更新只允许旧版号小于新版本；无写入时回读同租户同 id 六项载荷，仅完全同版同载荷视为幂等重放，否则 `TOOL_BINDING_VERSION_CONFLICT`。新建与递增版本不变，错误事务不提交覆盖行。原 HTTP 路由只对精确冲突映射 409，其他异常不吞；不改表、API path、解析器和 Receipt。 |
| 专项/相邻 | 新路由用真实 Store/Principal 的版本冲突测试先 RED exit1（原异常直冒出），再 409 正向。`.venv/bin/pytest -q tests/aip/test_e17_s3oq_tool_binding_issuance_pg.py tests/aip/test_w_l20_assignee_resolution.py tests/aip/test_w6_01_exact_assignee_resolution.py tests/aip/test_e17_s3of_issuer_acl_pg.py --disable-warnings --tb=short -o log_cli=false` exit0，17 passed/2 既有 xfailed、7 warnings；`py_compile` 和 `git diff --check` exit0。 |

复审：版本门防同版覆写/倒退，但原 HTTP `admin/executor/aip_executor` 写路径、普通 runtime 的 ToolBinding SIUD、缺写入 Receipt、缺独立 issuer/正式来源仍未修。Resolver 产生的是**解析** Receipt，不能代替发行 Receipt。原 `upsert` 可在高版本改变绑定，仍须正式来源、审批、exact 关联与身份门。当前服务若只重载 API，须先签名预检，并明确不宣称全栈重启；Host/worker/Provider保持关闭。下一波先设计最小 ToolBinding 写入来源/Receipt 与发行身份合同，再在隔离库 RED；当前卷 ACL/OIDC 迁移另波。

在线复验：提交 `m1@9864fdfd` 后签名预检 exit0 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`，只对 API 执行 `launchctl kickstart -k`；首次立刻 `curl --retry 5` 退出7、health000，进程仍在装载。查看 launchd/log 和端口后 PID50164 已 LISTEN，二次 `/v1/health`、`/v1/ready`、`/openapi.json` 与 Web `/aip/skill-publish` 均200，18181 CLOSED；日志明确 migration disabled、Host/worker关闭。首次探针是启动窗口，已复验并保留失败证据。此为 API 局部重载，不替代今日早前的 PG/API/Web 完整重启，也不证明正式受限 API 或首链。
