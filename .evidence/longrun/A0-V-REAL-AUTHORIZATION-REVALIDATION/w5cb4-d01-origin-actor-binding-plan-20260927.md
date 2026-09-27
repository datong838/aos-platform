# W5CB4 D01 原链 actor 绑定计划（2026-09-27，编码前）

## 上位方案与边界

231 A1-02/03 与 231-9 BG-02/03 要求自然来源、同租户当前身份和原 Owner，不允许开发者手工接线或借别人的原链发 AgentRun。W5cam/W5can 已有未注册的 `NaturalD01AtomicCoordinator`；当前新库无新鲜 TaskRun/Method/AgentRun，Host/Provider 仍关闭。本波只修复未来接线前的 actor 边界，不伪造 D01 来源包、不创建真实 Run，也不把单元绿称自然业务。

## 文件级顺序

1. `services/aos-api/tests/extension_runtime/test_ecommerce_analyst_d01_atomic.py`：先写 RED，证明外部传入 actor 与 `AnalysisContinuationOrigin.context.analysis.source.actor` 不同时，必须在连库和 Owner 前拒绝；相同 actor 保持原路径，原键 Receipt/未知提交测试不退化。
2. `services/aos-api/aos_api/ecommerce_analyst_d01_atomic.py`：在任何连接或来源读取前做精确 actor 同一性约束；不改变公共 AIP Owner、原事务锁/Receipt/commit、Provider/Host 开关。若原 context 无 actor，fail closed。
3. 专项、相邻累计、`py_compile`/diff；本波无新页面，浏览器验收只复核安全预览仍禁入。代码/方案一致性与跨租户、未知结果复审；verification→精确 m1 commit→AOS/Prime 上下文与 D-waves 更新。

## 退出/停止

只声明 D01 actor 绑定代码门，**不声明生产 selector、合法来源、真实 D01 结果、预算或模型可用**。不读商城源；旧 12 Run 不重播，未知结果不补发，不手工 `run_definition`；m1 单写不 push，`dev-org/dev-project` 仅零 canary，230 L0 挂起。现有用户未提交文件不动。
