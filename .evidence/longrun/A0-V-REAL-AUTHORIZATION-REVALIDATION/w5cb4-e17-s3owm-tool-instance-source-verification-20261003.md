# E17-s3o-w-m｜ToolBinding Agent 当前来源门验证

基线 `m1@513331ba`、Authority `AOS-001223`。按同前缀方案，只补原 ToolBinding active 写命令的当前同租户 AgentInstance 门。当前真实库只读，测试仅用 pytest 隔离 PG，未启 Host/worker/Provider，未改 migration、公共请求字段或正式 ACL。

| 项目 | 新鲜证据 |
|---|---|
| RED | `cd services/aos-api && uv run pytest -q tests/aip/test_e17_s3owm_tool_instance_source_pg.py` → exit1，5 failed/1 passed。缺失、provisioning、suspended、deleted Agent 仍可写 active ToolBinding；HTTP 缺失 Agent 也未拒绝。 |
| 最小修复 | `aip_assignee_resolution_store.py` 在原写事务内按 `org_id/project_id/instance_id` 查 Agent，active 请求仅接受 status active；`aip_assignee_authority.py` 把结构化阻断映射 409。disabled 仍能撤销；原解析每次重查 Agent。旧版本门测试和 Receipt strict xfail 各补真实 test-only Agent 前置。 |
| 专项+相邻 | `uv run pytest -q --disable-warnings --tb=short tests/aip/test_e17_s3owm_tool_instance_source_pg.py tests/aip/test_e17_s3oq_tool_binding_issuance_pg.py tests/aip/test_e17_s3or_tool_binding_source_receipt_pg.py tests/aip/test_w_l20_assignee_resolution.py tests/aip/test_w6_01_exact_assignee_resolution.py` → exit0，18 passed/1 strict xfailed。该 xfail 仍是原发行命令缺同事务 RegistryReceipt。 |
| 静态 | `python3 -m py_compile` 五个改动 Python 文件 → exit0；目标 `git diff --check` → exit0。`uv run ruff check` → exit2，当前 venv 未安装 ruff，不计 lint GREEN。 |

复审：负例失败前无 binding 行；active Agent 可正常发行，Agent 后停用使原解析禁入，且旧 binding 可改 disabled。所有新测试只向 `org-org/dev-project` 隔离库写 test-only Agent，没有 `dev-org` 写入。仍缺正式 Tool 来源、专用非 owner issuer、同事务发行 Receipt、runtime ACL 和当前实例 OIDC/绑定；此切片不证明正式首链。无 UI/schema 变更，浏览器适用性低；原现网准入仍由前一轮完整重启及浏览器三 blocker 证据约束。
