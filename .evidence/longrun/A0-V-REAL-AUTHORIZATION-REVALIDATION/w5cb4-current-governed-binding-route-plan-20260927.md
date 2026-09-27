# W5CB4 当前六实例受治理绑定前置核查计划（2026-09-27，方案先行）

## 上位方案与目标

按 231 主序 A0-V→A1、231-9 BG-00/BG-03/BG-04 和栖月汇首链方案，复用 AIP AgentInstance，不创造第二身份权威。当前六实例仅 `provisioning`，37 SkillTemplate 为 `evaluated`；本波只读查明最小合法绑定的依赖、Owner 和阻断，不运行模型、不启用 Runtime、不读商城源数据、不把测试/提交当自然首链。

## 文件级步骤

1. 核 `services/aos-api/aos_api/aip_skill_publication_service.py`、`aip_skill_registry.py`、`aip_skill_binding_readiness_service.py`：逐门记录发布、绑定、健康准入的精确依赖；核相关测试所证明的负向边界。
2. 核 `services/aos-api/aos_api/aip_capability_binding_service.py`、`aip_responsibility_profile_store.py` 与现有实例/定义证据：区分可安全准备的结构与需要真实身份、预算、模型/能力健康的运营准入。
3. 只读检查当前 8080/8434 状态和 m1 工作树；不启用 18181/Cron/worker，不运行任何会生成新业务 Run 的入口。
4. 更新波次总索引的紧邻下一步，写 verification、提交本波证据。下一编码波必须先选最小首链 Skill/Capability 和 exact 正式发布/配置来源，列明代码文件、测试与审批/外部调用停止门，再开码。

## 退出/停止

本波只以代码/方案/当前证据一致性结论退出，不宣称 Skill 已发布或实例可运行。任何来源不明、发布门缺失、身份/预算/健康未知继续 fail closed；禁止 SQL 改生命周期、伪造 Eval/Receipt、重放旧 Run、手工 run_definition 或未知结果重发。`dev-org/dev-project` 仅零 canary，230 L0 挂起，m1 单写且不 push。
