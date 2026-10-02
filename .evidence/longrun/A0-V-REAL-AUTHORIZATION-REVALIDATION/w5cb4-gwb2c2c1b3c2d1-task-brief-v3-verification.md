# GW-b-2c2c1b3c2d1｜原阶段来源 Task/Brief v3 骨架验证

日期 2026-10-02；起点 `AOS-001121` / `m1 b1d7bf5b`；依据同名 plan 与 231-5 §9。此切片只给原 Task/Brief Owner 提供一个独立的持久化来源骨架，**Host execute、正式实例与自然首链均未解禁**。

| 验证 | 命令/实测 | 退出码 |
| --- | --- | --- |
| RED | `pytest -q test_ecommerce_review_task_brief_authority_pg.py::test_accepted_stage_task_brief_v3_persists_one_original_artifact_and_exact_source`，经当前 signed preflight 只取得测试连接参数；pytest `conftest.py` 自动建销 `aos_test_*_ti4_test`。旧 `_review_lineage` 读取不存在的 `reviewIssueRef`，`KeyError`，1 failed。 | 1 |
| 专项 GREEN | 同一文件 `pytest -q`；原 Task/Brief Owner 同一外事务写入 v3 `schemaRef`，Handoff hash、Task.goal、Brief.spec 绑定相同的 16 项 `sourceLineage` 与单原 `Artifact`。同一 key 重放结果一致；改变原 StageDecision 后 `AipTaskIdempotencyConflict`；rollback 后 Task/Brief 均0。 | 0；4 passed |
| 相邻回归 | `pytest -q` 四文件：`test_ecommerce_review_task_brief_authority_pg.py`、`test_ecommerce_review_advance_host.py`、`test_ecommerce_review_handoff_content_runtime.py`、`test_ecommerce_content_generate_handoff_lineage_pg.py`；共49 passed、7 warnings。 | 0 |
| 静态与差异 | `python -m py_compile` 两改动文件、`git diff --check`。 | 0 |
| 浏览器禁入 | 已打开 `http://127.0.0.1:8434/aip/skill-publish`：37 仅已评测、0 发布；首条缺正式发布决定/Logic/模型路由三项，`发布此修订` disabled；电商工作台目录暂无可见入口。此页仅证明禁入，不证明本切片业务通过。 | 只读 |
| 当前运行门 | 当前签名 preview preflight 指向 `aos_current_preview_20260927`；`lsof -nP -iTCP:18181 -sTCP:LISTEN` 无监听（退出1）。真实库无本波写入、Host/worker/Provider 未启。 | 预检0／lsof1 |

复审：旧 Issue 分支的 Handoff body 字段、Task/Brief v1/v2 与四 Artifact 校验未放宽；新分支先经 `_strict_review_accept_command` 的完整 request hash/exact refs 校验，再由原 Task/Brief Stores 同事务创建并读回 hash。`ReviewAdvanceHostService.revalidate` 对新分支仍抛 `accepted stage Handoff Task/Brief is not wired`，`execute` 仍抛 `Owner is not wired`，`verify_receipt` 仍返回空；因此此代码不能独自接受 Handoff。测试中的阶段命令仅证明结构/Owner 写入能力，不是真人决策或当前正式授权。

剩余风险与下一波 `GW-b-2c2c1b3c2d2`：v3 尚无 bundle 内容生成、可读 Artifact、内容评审消费者的单原 Artifact/StageDecision 同源验证，原消费者仍要求四 `ArtifactRevision` 与 `ReviewIssue`；阶段 Eval/permission 的原生产者全链也待联合验证。先按 plan 第3项做 bundle 与宿主生成/评审的分支 RED/最小接线，旧 Issue 路径维持原样；全部消费者正反链之前不解除 Host `revalidate/execute/Receipt` 禁入。当前正式 OIDC/独立身份、八配置、Growth1.13 正式信任根和 binding 仍缺，当前实例另门处理。无商城源读取、旧12 Run重放、手工Run、dev-org写或push。
