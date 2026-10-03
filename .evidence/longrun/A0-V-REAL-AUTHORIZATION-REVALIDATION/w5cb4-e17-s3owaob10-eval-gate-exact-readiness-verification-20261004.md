# E17-s3o-w-ao-b10｜EvalGate 精确引用与评估时点验证

## 依据与 RED

- AIP-4 原 `AipEvalAuthorityStore.require_exact_passed` 要求 EvalGateDecision 类型、revision1、同租户 id/hash/status、有效期和可选 exact target；模型 Route resolver 已调用该权威方法验 target。BIND-1/231 要求配置 exact 且失效关闭。当前正式租户 `aip_release_gate_decision` 0，不能以测试行冒充正式 Eval。
- `PostgresBindingDependencyAuthority.eval_gate_passed` 之前只看 id/hash/status/本机墙钟，漏 ref 类型/修订，也无法使用绑定本次 `evaluated_at`。在 `test_aip_binding_readiness_service.py` 加定向代码诊断：匹配行给错 revision2，原返回 true；传入评估时点，原方法 TypeError。目标初跑 `2 failed`/exit1；测试连接为代码级 fake，正式业务通过仍只看当前库与运行链。

## 最小修复与回归

- 仅改 `aip_binding_readiness_service.py` Protocol/原 Postgres reader/唯一调用点：要求 `EvalGateDecision`、revision1、timezone-aware `evaluated_at`，按此时点比较 `decided_at <= evaluated_at < expires_at`；route resolver 保留其原 canonical exact target 验证。测试 Authority 接口同步该参数，无新表、migration、公开 DTO 或权限调整。
- 目标 `2 passed`/exit0；`test_aip_binding_readiness_service.py`、`test_e17_s3oo_capability_reader_pg.py`、`test_aip_skill_binding_readiness_service.py`、`test_aip_model_runtime_resolver.py` 累计 `48 passed`/7既有 warnings/exit0。py_compile 与精确 diff check exit0。
- 原 HTTP 绑定评估路由在 `routers/aip_bindings.py` 使用服务端 `datetime.now(UTC)`；激活时 `AipCapabilityBindingService.update` 另在写前取 `decision_at=datetime.now(UTC)` 并重算 readiness。代码复审显示本次评估钟不会被请求体直接回填；没有正式 Gate 行，当前实例仍禁入。

## 当前运行门

本证据初写时运行 API 尚未重载新代码，须精确提交后用原权威卷135、独立可恢复全备与签名安装来源做 PG→API→Web 完整重启和浏览器失败封闭复验，才可称 live 装载。正式 Model/Route/EvalGate、六 Binding、Host 与自然首链均 pending。
