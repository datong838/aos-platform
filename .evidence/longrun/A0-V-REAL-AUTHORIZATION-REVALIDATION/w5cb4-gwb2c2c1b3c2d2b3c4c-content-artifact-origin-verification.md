# d2b3c4c 已接受方案内容产物来源保持验证

上位231-5 §9；方案同目录 `w5cb4-gwb2c2c1b3c2d2b3c4c-content-artifact-origin-plan.md`。只验证隔离 PG 结果消费机制；正式 G2、原 Stage Owner、Host/Provider 与当前实例均未放行。

1. 测试夹具初次运行先在旧 `a0v_111` 固定断言失败；当前代码头为 `a0v_135`。两处断言改为读取 Alembic 唯一代码头，未更改生产迁移或权威库。随后有效 RED：新来源受控结果已落库，但 `consumed["artifact"]["sourceKind"]` 抛 `KeyError`；1 failed/8 deselected，退出1。
2. 最小实现：`ContentResultConsumer.consume` 对显式新来源先经现有 `_strict_content_generate_command` 核请求散列、单个原 `Artifact` 与精确 refs；仅该来源把 `sourceKind=accepted-stage-v1` 纳入可读 Artifact payload、canonical hash 和持久 metadata。未知来源拒，旧四 `ArtifactRevision` 路径不新增字段；Usage/Budget settle/Receipt-first 保持原逻辑。
3. 隔离 PG 受控结果链新用例通过：落库 metadata、`aip_artifact.content_hash` 与 `ReadableContentArtifact.from_payload` 同源；同命令重读幂等。旧来源在共用消费 helper 断言没有 `sourceKind`。全文件排除一个已登记 RETURN Action 正向用例为 `8 passed, 1 deselected`；相邻三文件 `46 passed, 1 deselected, 7 warnings`，退出0。`py_compile`、`git diff --check` 退出0。
4. 未排除时的全量回归为 `46 passed, 1 failed`，唯一失败仍是旧 `test_original_settled_artifact_runs_current_content_subject_eval[RETURN]` 在 `AipActionStore.create_proposal` 命中 `REPAIR_ACTION_CURRENT_AUTHORITY_UNWIRED`。此门在 E17aa3b0/BG00k 已登记；不得把测试 checker 或伪 Preview 当正式 RETURN Action producer。本波未更改该门，也不报全量 GREEN。

风险与下一步：当前增长包 `execute_content_capability` 和 Host 生成 `execute` 对新来源仍显式禁入；原 Review Receipt/正式 G2 产出、内容专属 Eval/ReviewIssue、人类 ACCEPT/RETURN 同源联合、正式身份/八配置/绑定与自然首链仍缺。需要继续 d2b3c4c 后续消费者和正式来源，不可从此产物形状测试推断当前业务已产出。
