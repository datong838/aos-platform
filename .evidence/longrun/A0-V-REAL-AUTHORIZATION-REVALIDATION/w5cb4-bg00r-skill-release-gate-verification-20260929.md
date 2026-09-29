# W5CB4 BG-00r｜Skill E2 Gate/Publication 未证明执行来源禁入验证

方案：`w5cb4-bg00r-skill-release-gate-plan-20260929.md`；基线 `aos-platform/m1@c735f233`、权威 `AOS-000866`。只改 `aip_release_publication_service.py` 及隔离 Skill 测试，不新增迁移，不写当前库。

## RED / 实现 / 回归

- RED：`services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_aip_skill_publication_service.py::test_unattested_skill_report_cannot_derive_release_gate` 退出 1，`Failed: DID NOT RAISE AipReleaseGateRejected`。隔离 helper 使用 `test-only://` source 和注入 lambda，经旧 `run()` 生成 Report，现有 E2 会把它派生为 PASSED Gate。此测试并非正式业务来源。
- 最小实现：`derive_gate` 同租户核 Report/Run/Suite exact 后、写 Gate 前，对 Skill target 抛 `AipReleaseGateRejected("formal Skill Eval executor authority unavailable")`；`publish` 对已存在 Gate 的 Report 复验时同样拒绝 Skill，阻止旧 PASSED Gate 产生新的 PublicationEvent。已有 Event 的同 key 回放不产生新事件，历史行不改写；LogicGraph 路径无变化。
- 新增隔离测试精确种下一个既有 PASSED Gate，再调用 `publish`，断言拒绝且 PublicationEvent=0；这只是旧 Gate 兼容风险的负向测试，不能证明 Gate 合法。旧名为 `test_real_eval_publication...` 的 lambda 正向测试保留为 `strict=True` 的 `xfail`，清楚记录正式 signer/Receipt 尚缺；意外通过会使测试失败。真实正向验收尚未达成。
- 专项：新两负向及旧正向占位 `2 passed, 1 xfailed`，退出 0。Runner/Registry/E2/Skill 相邻累计命令 `services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_aip_eval_runner.py services/aos-api/tests/aip/test_aip_eval_pack_registry.py services/aos-api/tests/aip/test_aip_release_publication_service.py services/aos-api/tests/aip/test_aip_skill_publication_service.py`，`30 passed, 1 xfailed`、退出 0。两文件 `compileall -q` 与 `git diff --check` 退出 0。
- 当前权威库 `BEGIN READ ONLY`：`aos_current_preview_20260927@a0v_111`，栖月汇 EvalRun/Report/Gate/PublicationEvent `0/0/0/0`，退出 0。隔离测试写入仅在 test-only PostgreSQL；未读商城源、未启动 Host/worker/Provider、未重放旧 12 Run、未动 230 L0。
- 提交 `m1@53910d92` 后，原签名 Receipt 的当前代码预检退出 0、`CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`（approved 安装、四个 published bundle、Runtime Binding 0）。旧 API session `89019` Ctrl-C 后退出 0，8080 无监听；新 session `25277` 用最新代码和同一 Receipt 启动，8080 健康/就绪和 8434 Skill 页面各 200，18181 无监听。数据库/Web 未重启；今日 09:04 完整重启证据仍独立存在。

## 复审结论和下一步

BG-00q 与 BG-00r 合起来使缺执行权威的正式 Skill Contract Runner、E2 新 Gate 和从旧 Gate 新发 PublicationEvent 都失败封闭。**还没有**正式 Judge/Target signer、撤销、执行 Receipt、G2 来源内容和 MinIO 真实读回；正向 Skill Eval/发布、D01 与自然首链均未通过。现有历史 PublicationEvent 若被其他下游复用也需独立审计，不能因本波读旧事件而宣称新发行安全。下一波应先定位/定义真实签发 Owner 和可验证执行 Receipt，再在隔离克隆证明正向，而不是增加环境开关或测试回调例外。
