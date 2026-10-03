# E17-s3o-w-ao-b10｜EvalGate 精确引用与评估时点验证

## 依据与 RED

- AIP-4 原 `AipEvalAuthorityStore.require_exact_passed` 要求 EvalGateDecision 类型、revision1、同租户 id/hash/status、有效期和可选 exact target；模型 Route resolver 已调用该权威方法验 target。BIND-1/231 要求配置 exact 且失效关闭。当前正式租户 `aip_release_gate_decision` 0，不能以测试行冒充正式 Eval。
- `PostgresBindingDependencyAuthority.eval_gate_passed` 之前只看 id/hash/status/本机墙钟，漏 ref 类型/修订，也无法使用绑定本次 `evaluated_at`。在 `test_aip_binding_readiness_service.py` 加定向代码诊断：匹配行给错 revision2，原返回 true；传入评估时点，原方法 TypeError。目标初跑 `2 failed`/exit1；测试连接为代码级 fake，正式业务通过仍只看当前库与运行链。

## 最小修复与回归

- 仅改 `aip_binding_readiness_service.py` Protocol/原 Postgres reader/唯一调用点：要求 `EvalGateDecision`、revision1、timezone-aware `evaluated_at`，按此时点比较 `decided_at <= evaluated_at < expires_at`；route resolver 保留其原 canonical exact target 验证。测试 Authority 接口同步该参数，无新表、migration、公开 DTO 或权限调整。
- 目标 `2 passed`/exit0；`test_aip_binding_readiness_service.py`、`test_e17_s3oo_capability_reader_pg.py`、`test_aip_skill_binding_readiness_service.py`、`test_aip_model_runtime_resolver.py` 累计 `48 passed`/7既有 warnings/exit0。py_compile 与精确 diff check exit0。
- 原 HTTP 绑定评估路由在 `routers/aip_bindings.py` 使用服务端 `datetime.now(UTC)`；激活时 `AipCapabilityBindingService.update` 另在写前取 `decision_at=datetime.now(UTC)` 并重算 readiness。代码复审显示本次评估钟不会被请求体直接回填；没有正式 Gate 行，当前实例仍禁入。

## 当前运行门

代码提交 `m1@ef1f9e94` 后，使用原权威命名卷 `colima-aos-extension/aos-a0v-recovery-pg-data`，按 PG→API→Web 顺序完整重启；PG 立即 `pg_isready` 首查 exit2，随后重试 exit0。新 API/Web PID 58016/58037，18435/8080/8434 LISTEN，18181 无监听，Host/worker/Provider 保持关闭。当前代码与库迁移均 `a0v_135`；`/v1/health`、ready 和八工作台路由均 HTTP 200，旧 `/v1/tools` HTTP 404、OpenAPI 旧路由 0。原卷只读核对 Installation1、RegistryReceipt6、ReleaseGate0、CapabilityBinding0、Host assignment0。此前独立完整恢复并逐表对账的当日全备 SHA `28b356f3…b6f1` 保持在 `aos-recovery/.aos-current-backup-20261004-s3owaob3`，本轮未对原库写入。

重启后签名 receipt 预检 exit0：安装 approved、4 个 publishedVersions、runtimeBindings0，签名树仍是 `.aos-current-build-pyGkqQ`。CUA 浏览器重载 `/aip/skill-publish` 并截图复核 `org-org/dev-project`：37 条仅评测、0 发布，正式技能发布决策/事件、当前已发布 Logic、可用模型路由/策略三项阻断仍在，发布按钮禁用，无可见电商工作台入口。截图经浏览器工具显示，本 verification 未另存 PNG，故以页面可复核状态和工具输出为证，不虚称文件截图已落盘。

此为新代码 live 装载及失败封闭，不是正式 EvalGate 或自然首链通过。正式 Model/Route/EvalGate、六 Binding、八配置、Owner、Host 与自然首链仍 pending。
