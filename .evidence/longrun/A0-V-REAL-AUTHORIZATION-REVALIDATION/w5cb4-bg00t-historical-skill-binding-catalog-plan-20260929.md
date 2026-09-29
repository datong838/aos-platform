# W5CB4 BG-00t｜历史 Skill Binding 与目录准入方案

## 上位合同与现状

231 首链要求真实安装、来源、权限与 Receipt 证明，不把页面可点或过往测试当业务完成。AIP-6 的 SkillBinding 必须引用组织级 exact Skill/能力/预算；BG-00q/r/s 已阻断新正式 Skill Gate、发布事件及旧记录再发行，但既有发布行的读取口尚未闭合。当前权威库 Gate/Event/published Skill 零行是现时事实，不替代代码门。

`aip_skill_binding_readiness_service.py` 当前仅核 Gate `status=passed`、`decision_hash`，以及最新 Event 的 published/target；未读取 Gate 的 EvalReport 来源。`aip_ecommerce_agent_installer.py` 目录只聚合已缓存的 available Binding 和发布生命周期；在历史可用 Binding 的 TTL 内可显示 runnable。两处均需以独立隔离测试复现。

## 文件级施工

1. `services/aos-api/tests/aip/test_aip_skill_binding_readiness_service.py`：补历史 Skill Gate/Event 的负向测试；浅层状态齐全但正式 Eval 执行权威缺失时必须 BLOCKED。隔离测试假连接补完整 Gate/Report 行；原“正向”假权威用严格 xfail 保留为待正式 signer/Receipt 落地的合同，不作为通过证明。
2. `services/aos-api/aos_api/aip_skill_binding_readiness_service.py`：在同租户连接内核完整 Gate 行、有效期、source Skill parent exact target 与 Event 所指 Gate，复用 E2 `_gate_from_row` 与 `_verify_gate_evidence`，拒绝 Skill 缺正式执行权威；无新写、无新权威定义。保留原撤销/租户/预算/模型路由检查。
3. `services/aos-api/tests/aip/test_aip_catalog_item_runtime.py` 与 `services/aos-api/aos_api/aip_ecommerce_agent_installer.py`：隔离 RED 证明 cached available 可使历史 Skill runnable；目录 read-only 重新评估 exact Binding，对评估失败/阻断时按 unavailable 显示，不能靠旧 TTL 绕过。需兼容无绑定和定义空态，不触发刷新写库。

先 RED、最小实现、专项/相邻累计回归、编译/差异复审、签名 API 新代码重载。当前库只读；不迁移、不触发 Host/worker/Provider/商城源/旧 Run。回滚为精确撤销本波代码提交；正式 Judge/Target signer/撤销/执行 Receipt、G2 来源和 MinIO 真实读回继续下一波。
