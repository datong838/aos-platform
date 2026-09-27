# W5CB4 当前受治理绑定路线核查 verification（2026-09-27）

## 第 1/4 步：上位方案与现场

复习 231 主序 A0-V→A1、231-9 BG-00/03/04 及栖月汇首链：六数字同事复用 AgentInstance，首链要求自然事件、exact 评审、受控内容能力与回流；隔离准备不算自然业务验收。以 m1 `c0dd4812` 为起点，当前唯一未提交项为既有用户测试改动及 w5c8i 两文件，均未动。

## 第 2/4 步：正式门与最小路径

- `aip_skill_registry.py` 拒绝普通 Registry 直接创建 published Skill；`create_binding` 要求同租户已发布 Skill、最新修订也是 published，并要求 CapabilityBinding 覆盖所需能力。
- `aip_skill_publication_service.py` 的正式新修订要求 exact evaluated 来源、passed release gate、published PublicationEvent、exact 已发布 LogicRevision、active ModelRoute/RuntimePolicy 与对应 Eval gate；它在新修订上写入 publicationTenant 与 exact 引用，不修改 evaluated r1。
- `aip_capability_binding_service.py` 只从 published CapabilityRevision 创建绑定；定义 published 不等于绑定 active。`aip_skill_binding_readiness_service.py` 进一步要求实例 active、CapabilityBinding active 且健康未过期、模型路由/预算政策一致，缺项返回 blocked。
- 因此下波顺序为：选首链最小 Skill/Capability → 正式 Eval/Logic/route/预算与发布证据 → 正式 CapabilityBinding → SkillBinding → ResponsibilityPlan/Runtime 准入。不得把 37 Skill 全量发布作为首链前置，也不得 SQL 改 lifecycle 或用测试 fixture 冒充真实权威。

## 第 3/4 步：只读检查与复审

8080 `/openapi.json`=200，8434 `/aip/model-runtime`=200；18181 无监听。没有执行业务入口、没有新的 Run/Receipt、没有读取商城源。本波无代码变更，故无新增逻辑专项测试；现有 `test_aip_skill_publication_service.py` 与 `test_aip_skill_binding_readiness_service.py` 可作为下波专项基线，不能代替当前实例验收。

## 第 4/4 步：结论、风险与下一波

本波仅确定依赖图并更新 `docs/palantier/AOS项目开发上下文/228-2026-09-27-AOS长程波次总索引.md`；六实例仍 provisioning，Skill/Capability/Runtime binding 仍按上一波独立读回为 0，本波未重查数据库，不能宣称现时绝对值。下一波先复习各 Owner 的正式发布/配置入口并细化文件级最小首链集合，再作最小编码、专项/累计、浏览器、复审、verification 和 m1 提交。任何来源/预算/健康未知继续禁入。
