# d2b3c4d 内容人工评审来源命令验证

上位 231-5 §9；文件级方案 `w5cb4-gwb2c2c1b3c2d2b3c4d-content-review-source-plan.md`。本次仅完成判别式命令入口，原内容 Eval/ReviewIssue、人类 ACCEPT/RETURN、Artifact/v3 Brief/Stage Owner 读者仍须完整接线；当前实例不启 Host/Provider。

1. RED：新增 `test_accepted_stage_content_review_command_keeps_single_original_source`，从受控可读 Artifact 构造 Review 请求，在 bundle `ContentReviewRequest.__post_init__` 报 `accepted stage content review Host is not wired`；`1 failed, 31 deselected`，退出1。受控 Artifact 与字符串 `content-eval-issue` 仅为合同测试输入，不是原人工批准或正式内容 Eval。
2. 最小实现：bundle 仅新来源在 review command 加 `sourceKind=accepted-stage-v1`；宿主严格解析器按来源分支要求一个原 `Artifact` 或旧四 `ArtifactRevision`，requestHash 包含来源种类。错分支/四旧引用均拒；ReviewIssueRevision、ReviewerAuthorityRevision 和 ACCEPT/RETURN 的原字段仍必填。未修改签名 1.13 候选树，也未让宿主下游 `_artifact_authority`、`_task_brief_authority`、`_issue_authority`、`execute` 通过新来源。
3. 专项+相邻：`test_ecommerce_content_capability_budget_runtime.py` 与 `test_ecommerce_content_review_authority_feedback.py` 共 `43 passed, 7 warnings`，退出0；三文件 `py_compile` 和 `git diff --check` 退出0。旧 Issue Review 合同负例仍在相邻套件中通过。尚未做原 Stage/Review Receipt 与内容专属人工事件的隔离 PG 联合正向，也未对当前真实库写入。
4. `m1@5f5a3b21` 后重载既有 API LaunchAgent；首次立即探测 8080 尚未监听（启动瞬态），再次读回 PID49995、health/ready 各200，8434页面200，18181未监听。浏览器刷新后读回电商工作台无可见入口、37项仅评测/0发布、三项正式来源缺口和 disabled 发布按钮；截图 `w5cb4-gwb2c2c1b3c2d2b3c4d-browser-20261002.jpg`（JPEG，SHA256 `8de4dbc8d778ed9333417f25827448798b7adf948f1791314a40a12a59062746`）。该页面状态验证禁入，非完整 PG/API/Web 再启动，也非真实业务通过。

风险：包内请求可构造不等于人工评审可执行；宿主 Artifact 仍按旧无 `sourceKind` 的四来源可读形状核验，v3 Brief/原 Stage Owner 与内容 Eval/ReviewIssue 仍需判别式联合验证。下一切片先用可销毁 PG 做原持久来源与内容专属 Eval/人工事件的 RED，再接宿主各读者和 Receipt/反馈、ACCEPT/RETURN 同事务状态。正式 G2、OIDC、八配置、Host identity/assignment、binding、Growth1.13 正式发布与自然首链另门。
