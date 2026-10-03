# E17-s3o-w-ao-b10｜EvalGate 精确引用与评估时点方案

## 上位和代码事实

复习 AIP-4 E2、AIP-WKS-DEP-0B-R1-04/R1-05、231/BIND-1。原 `AipEvalAuthorityStore.require_exact_passed` 要求 `EvalGateDecision`、修订1、同租户 decision/hash、passed、`decided_at <= now < expires_at`，并可验目标 exact ref；模型 Route resolver 已经通过它做目标校验。Capability Binding 的 `PostgresBindingDependencyAuthority.eval_gate_passed` 另以 decisionId/hash/status/本机现在时间直读，漏验 ref 类型/修订，且与上层 `evaluated_at` 不同钟；当前正式租户 ReleaseGateDecision0，不能造当前正向。

## 文件级最小施工

1. 在 `services/aos-api/tests/aip/test_aip_binding_readiness_service.py` 加真正消费 `evaluated_at` 的断言；在隔离测试中用原 ReleaseGateDecision 行/受限 Reader 或精确 fake connection 复现错类型、修订2被原 Binding reader 接受以及评估钟与墙钟不一致的 RED。测试 fake 只作代码诊断，不能替代当前正式来源或运行验收。
2. 只改 `services/aos-api/aos_api/aip_binding_readiness_service.py` 的 Protocol、Postgres 实现和唯一调用点：要求 ref 类型 `EvalGateDecision`/修订1，按传入的 timezone-aware `evaluated_at` 核既有 status/hash/有效期；原 route resolver 继续通过 canonical authority 验 exact target。不另建第二评测源或数据表。
3. 专项及相邻测试，检查 API 入口的 `evaluated_at` 来源、激活前重算/当前时钟、Model/Route 当前性和错租户，之后按需最新代码原卷质量重启及浏览器验收。当前库只读、Host/worker/Provider关；无正式 EvalGate、六 Binding/首链仍 pending。

边界：org-org/dev-project 唯一正向，dev-org 零副作用；不读商城源、不重放旧12 Run、不手工 Run、不碰230 L0、不 push。
