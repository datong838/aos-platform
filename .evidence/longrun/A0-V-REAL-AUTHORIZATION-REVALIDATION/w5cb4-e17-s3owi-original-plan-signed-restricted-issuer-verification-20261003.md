# E17 s3o-w-i 原 Plan 签名来源受限发行验证

基线 `aos-platform/m1@dff21876`，Authority `AOS-001217`。按 231-3/4/5/9、栖月汇方案及 D-wave s3o-w-i；先落本波文件级计划，再动测试。当前真实库 `aos_current_preview_20260927@a0v_135` 只读，本波无生产代码/迁移/API/UI 改动。

## 运行及 RED→GREEN

| 检查 | 命令/结果 |
|---|---|
| 签名来源 | 回执 `.aos-growth-113-signing-receipt-20261002-r1.json` 为 `SIGNED_TREE_GREEN`，签名树、信任根文件存在；原 `_signed_release()` 校验树 hash、key ID、trust root、每个制品内容 hash 与 ReleasePolicy。仅隔离本地发行。 |
| 首次环境失败 | `AOS_DATABASE_URL=postgresql://postgres@127.0.0.1:18432/postgres ... pytest test_growth_signed_installation_full_schema_pg.py`，exit1，迁移 `GRANT ... TO aos_app` 因 18432 测试容器无 `aos_app` 角色而失败；未进入 OCI。 |
| 原全链基线 | 将 `AOS_DATABASE_URL` 指向 18435 当前集群作为**创建一次性 `aos_test_*_ti4_test` 的连接**，设置 `AOS_EXTENSION_PG_TEST=1 AOS_EXTENSION_OCI_TEST=1 AOS_GROWTH113_SIGNED_RECEIPT=<上述回执>`，运行 `.venv/bin/python -m pytest -q --tb=short tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py`，原测试 `1 passed`，exit0；不在真实库写表。 |
| 新受限路径 RED | 首次加入 `plan_restricted_issuer_case.py` 后，原 BI prepare 被测试残留触发器以 `PLAN_RECEIPT_UNPAIRED` 拦住，整测 exit1；根因是 helper 清理遗漏，已在 `finally` 精确 DROP 该触发器与函数。 |
| 新受限路径 GREEN | 同一隔离签名全链整测 `1 passed, 7 warnings`，exit0，10.85s。新 helper 从原批准安装 resolver 精确核模板，独立 `LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS` 连接原 `AipProductionContractStore`：create/revise 原 head+revision+Receipt、同键回放、改输入冲突、错误版本拒绝、失败注入回滚、跨租户和无配对 Receipt 拒绝；无 active SkillBinding 时 freeze 拒绝且 Receipt 0。原 BI prepare/rebind/运行验证后续步骤同测试继续通过。 |
| 相邻回归 | `AOS_EXTENSION_PG_TEST=1 ... pytest -q --tb=short tests/extension_runtime/test_plan_receipt_writer_protocol_pg.py tests/test_w2b_production_contract_store.py` → `28 passed`，exit0。`py_compile`、`git diff --check` exit0。 |
| 清理与真实状态 | 当前集群只读查询：当前库 `a0v_135`，`org-org/dev-project` 原共享 Receipt 0、runtime binding 0；`s3owi_plan_%` 角色 0、`aos_test_%_ti4_test` 库 0；`docker --context colima-aos-extension ps -aq --filter label=aos.extension.owner` → 0。`/v1/health`、`/v1/ready`、`/aip/skill-publish` 均 HTTP 200，18181 无监听。 |

## 复审及边界

新 helper 只在自动创建的一次性全迁移库运行；直接登录的受限角色无超管、无继承和 RLS 绕过，密码仅进短生命周期测试连接，不落仓。Receipt 守卫要求相同租户的原 Plan 当前 head/revision/hash 配对，原 BI prepare 不受本 helper 影响；结束精确撤销策略/身份/触发器。原代码没有改动，浏览器 UI 也没有新路径，因此本切片无需新增截图。原全链内的六个 active AgentInstance 为隔离前置夹具，签名树为本地 test-only，不是当前正式发行身份。

本波仅证明 generic Plan create/revise 与失败封闭的 freeze。BI prepare 原测试通过，但其 Store 尚未由独立 Plan issuer 发行；successor 原写者、Content 原注册、正式 ACL/凭据迁移、当前 Growth 1.13 发布、八类配置、Host Owner/六 Binding 和自然首链仍待下波。不能把 test-only 签名或页面 200 当作经营闭环。
