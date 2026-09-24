# W5c4v 恢复权限拒绝的安全分类方案（2026-09-25）

上位 231 A0-V、231-9 BG-00；W5c4u 证明原 attempt 仅留下 `PermissionError` 类型，无法事后确认抛出分支；Host `_fresh_health` 超 3 秒门和有限再探测已有测试，不凭未知耗时改宽健康门。本波只改**未来拒绝的安全类型分类**，不改变现有权限谓词、异常基类、终态 code、数据库 schema、业务授权或旧 attempt。

## 文件级九步

1. 复习产品与技术边界：维持 fail-closed、无原始异常信息持久化，原 Store attempt 不重发；对照 `recoverable_store_attempt._terminal_failure` 仅持久安全类型名的合同，以及 `a0v_089` 类型名 regex。Host 时序现有 `test_preparation_owner.py` 的 bounded reprobe 与 `test_lease_renewal.py` 的 3 秒门保持不变。
2. 文件清单：本方案；`services/aos-api/aos_api/pipeline_snapshot_group_recovery_authority.py`；新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c4v_recovery_permission_classification.py`；本波 verification。不得碰迁移、Host 运行状态或商城数据。
3. 最小实现：为恢复 authority 中三种精确 `PermissionError` 分支定义固定英文安全子类（原 executor、当前 definition、当前 executor），只替换该三处 raise，保留原拒绝字符串及谓词。两处原 executor 使用同一子类。未来 attempt 的 `terminal_error_type` 可区分这些分支，但旧 attempt 仍为 `PermissionError`/UNKNOWN；其它组件拒绝不归因。
4. 专项测试先 RED：断言三子类仍是 PermissionError、固定安全类名满足数据库正则、`_terminal_failure` 对子类维持 `RECOVERABLE_EXECUTION_EXCEPTION` 且绝不含异常消息；静态核三处原谓词不变。再最小实现。
5. 累计回归：隔离测试库运行 W5c3/W5c4、原恢复合同、attempt/Host 续租相关测试；新增 logic 无数据写入。停止测试库后读回原组仍 WAIT_24H。
6. 浏览器只读验收：确认计划页可访问且没有因后端类型分类导致 UI 状态变化；页面不暴露异常分支则 `BROWSER_PARTIAL`，不运行/冲刷。
7. 一致性复审：类型名不能携带租户、凭证、原文、资源 ID；不改变原授权条件、旧 attempt/Run、3 秒健康门和 24h 正式收敛门。若 tests 暴露类型等值兼容风险，停止并退回方案。
8. verification 落盘提交后同步 AOS 上下文与 Prime 独立受管记忆，读回校验。
9. 下一波 W5c4w：重新只读评估严格 24h 时间与全门禁；若尚未过线，继续独立 Host 健康时序可证伪诊断，不用人为等待替代开发；过线则先新方案，再用正式 stalled Owner 一次性收敛。

本波禁令：不试运行旧 generation，不修改安全权限/异常成功语义，不将分类改善冒充旧失败根因已定位，不读取商城源行、不 push。
