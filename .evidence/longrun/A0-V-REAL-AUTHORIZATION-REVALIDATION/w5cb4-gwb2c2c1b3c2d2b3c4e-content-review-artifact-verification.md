# d2b3c4e 内容评审宿主 Artifact 同源读者验证

上位 231-5 §9；文件级方案 `w5cb4-gwb2c2c1b3c2d2b3c4e-content-review-authority-plan.md`。本次只完成第一项原内容 Artifact 精确读者，后续 v3 Brief、原 Stage/Review Receipt、内容 Eval/Issue 与人工决定联合仍未完成。

1. 可销毁 PG 受控内容结果已持久化 `sourceKind=accepted-stage-v1` 和单个原 `Artifact`，新增 `_artifact_authority` 正向读取及错 hash/跨租户负例。有效 RED 在旧 `_READABLE_CONTENT_FIELDS` 处报 `content review Artifact exact projection drifted`；`1 failed, 9 deselected`，退出1。
2. 最小实现仅新来源让 `_artifact_authority` 精确接收来源字段，重算内容 canonical hash，要求同租户单个原 Artifact 持久行与命令 exact ref 一致；旧四个 `ArtifactRevision` 路径保留。为防读者局部接线导致可执行，新来源 `revalidate/execute/verify_receipt` 均在数据库效果前显式拒绝 `Host is not wired`；新增 NoDatabaseEffects 三入口负例。
3. 新 PG 用例 1 passed；三文件相邻用 `-k 'not test_original_settled_artifact_runs_current_content_subject_eval or ACCEPT'` 得 `53 passed, 1 deselected, 7 warnings`，退出0；未排除全量 `53 passed, 1 failed`，唯一旧 RETURN Action 在 `REPAIR_ACTION_CURRENT_AUTHORITY_UNWIRED`，本波未改公共 Action 门。`py_compile` 与 `git diff --check` 退出0。所有新来源行均为可销毁 PG 测试来源，不是当前真实内容或正式人工 Eval。

限制：此读者可正向不等于 Host 允许评审；v3 Brief/原 Stage/Review Receipt/内容专属 Eval/Issue、人类 ACCEPT/RETURN、Receipt/反馈与 Run/Task 终态均未完成，正式 G2/OIDC/八配置/Host 身份/绑定/Growth1.13 正式发布和自然首链仍缺。当前真实库只读、Host/worker/Provider关闭。
