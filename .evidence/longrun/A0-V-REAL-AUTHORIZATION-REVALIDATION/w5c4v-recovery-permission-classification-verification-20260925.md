# W5c4v 恢复权限拒绝安全分类核验（2026-09-25）

上位 231 A0-V、231-9 BG-00；方案先行 `w5c4v-recovery-permission-classification-plan-20260925.md`，提交 `23cd13c9`；代码/专项测试提交 `0c7be246`。本波只改善**未来**拒绝的类型可观测性，不定位旧 `PermissionError` 的原抛出点，不重发旧 attempt。

## 九步执行记录

1. 复习原 Store attempt `_terminal_failure` 只存安全错误类型名的合同、`a0v_089` 正则、恢复 authority 原三个权限拒绝条件、Host 3 秒健康门与 bounded reprobe 现有测试。未更改 Host 健康逻辑。
2. 文件级范围：本方案、`services/aos-api/aos_api/pipeline_snapshot_group_recovery_authority.py`、`services/aos-api/tests/extension_runtime/test_a0v_w5c4v_recovery_permission_classification.py` 和本 verification。
3. 最小改动：定义 `OriginalRecoveryExecutorDenied`、`CurrentRecoveryDefinitionDenied`、`CurrentRecoveryExecutorDenied` 三个 `PermissionError` 子类，仅替换原恢复 authority 四个 `raise`（原 executor 两处）。原 predicate 与固定拒绝字符串不变；不改 schema、权限 grant 或业务数据。
4. 先 RED：隔离测试库 4 failed，均为目标类型/替换尚不存在；首次隔离库未启动报环境错误，启动后重新确认真实 RED。实现后定向含 attempt、lease、owner 的 **75 passed**。
5. 有界累计 W5c3/W5c4、定义 PG、未接受路径、attempt/lease/preparation **177 passed，7 warnings，21.79s**。额外扩大到恢复 Owner PG 全套的运行在 5m40s 时仍未结束，人工中止；当时 **187 passed** 只代表已执行部分，**不得当作扩展整批 GREEN**。隔离 `aos-dev-pg` 已停止，未用共享测试库。
6. 浏览器 5174 `/data/schedules` 只读看到 12 单路计划；整组 rev4 和未来错误子类不在此页面展示，`BROWSER_PARTIAL`。未点保存、真实同步或队列冲刷；临时页/前端已关闭。
7. 一致性/风险：三子类仍是 PermissionError；类名满足数据库正则、`RECOVERABLE_EXECUTION_EXCEPTION` 固定 code，原始异常消息不进入终态。检索未发现依赖 `type(error) is PermissionError` 的同模块消费者。**旧 attempt 保持 `PermissionError`，不追溯归因**。本波后只读资格仍 `STALLED_WAIT_24H`、`automaticAction=false`；定义 rev4 disabled、12 Run running、正式关闭/退休未完成。
8. 本 verification 先落盘提交，再 CAS 同步 AOS 项目开发上下文及 Prime 独立受管记忆并读回。
9. 下一波 W5c4w：重新检查严格 24h 和原组全门禁；若未到，继续可证伪的 Host 健康时序诊断/最小测试；过线后先独立文件级方案，再唯一正式 stalled Owner 收敛和定义退休。未知提交边界冻结，不补跑旧代。

安全边界：无商城源行读取、无业务库写、无 Host restart、无新 attempt、无 push；A0-V/BG-00 仍未过门，230 L0 挂起。
