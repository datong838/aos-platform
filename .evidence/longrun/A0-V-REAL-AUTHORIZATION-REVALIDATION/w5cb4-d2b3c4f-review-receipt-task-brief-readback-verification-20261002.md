# d2b3c4f Review Receipt 原 Task/Brief 同源读回验证

基线 `m1@d2bf1da8`、`AOS-001158`；方案见同目录 `w5cb4-d2b3c4f-review-receipt-task-brief-readback-plan-20261002.md`。只改 `ReviewAdvanceHostService.verify_receipt` 的 accepted-stage 分支和三处测试；当前真实库只读，Host/worker/Provider 仍关闭。

## RED 与修复

- 单个新 PG 测试 RED：`1 failed`，伪 Receipt 指向不存在的 Task 时原读者仍返回 Receipt。隔离测试库保留，未删库。
- 最小实现先验 Handoff exact ref，再复用原 `ContentReviewHostService._task_brief_authority`，同事务核 Task.goal、Brief.spec 中的来源及 Handoff、v3 schema、无外部发布。缺失、漂移或伪造原 Task/Brief 均返回空验证。旧来源与执行禁入不变。
- 相邻原 Stage 测试独立单跑仍 RED：`stage Handoff source chronology drifted`。临时诊断读回：草案 10:48:22.718485 UTC、Stage 决定 11:48:22.718485 UTC、批准 13:48:22.864351 UTC，而 PostgreSQL 当时钟 13:48:22.799640 UTC；宿主批准钟领先数据库约 65 ms。仅将隔离夹具批准时间注入为数据库 `clock_timestamp()`；原 Stage 单测随即 `1 passed`。临时诊断输出已移除，产品时序门未修改。

## 本轮新鲜验证

在 `services/aos-api` 执行 `AOS_DOTENV_DISABLED=1 AOS_EXTENSION_PG_TEST=1 AOS_TEST_RETAIN_DATABASE=1 .venv/bin/pytest -q tests/extension_runtime/test_ecommerce_review_task_brief_authority_pg.py tests/extension_runtime/test_ecommerce_review_advance_host.py tests/extension_runtime/test_ecommerce_review_handoff_content_runtime.py tests/extension_runtime/test_ecommerce_content_generate_handoff_lineage_pg.py tests/extension_runtime/test_analyst_stage_handoff_source_pg.py --disable-warnings --tb=short`，退出码 0，`77 passed, 7 warnings in 8.63s`。

`python -m py_compile` 四个改动 Python 文件退出码 0；`git diff --check` 退出码 0。浏览器路径没有改变，且当前实例正式 OIDC、Host、八配置与 Growth 1.13 发布仍缺，故不以页面 HTTP 200 或旧截图宣称业务验收。本波没有运行受限 Host、worker、Provider、自然首链或任何当前库写入。

## 一致性、风险与下一波

实现与方案一致：Receipt 本身无法单独证明原 Task/Brief；原 Store exact ref 与哈希在同一事务中可读才通过。测试正例是隔离 PG 原 Task/Brief 加局部 Receipt 读桩，**不是正式 G2/Review 原生产者证明**。`accepted stage Handoff Task/Brief is not wired` 和 `accepted stage Handoff Owner is not wired` 两个运行禁入仍保留。下一波继续 D-waves 登记的原 G2/Review producer 或 E17 正式签名/身份/八配置来源，缺当前合法来源时只封该实例。
