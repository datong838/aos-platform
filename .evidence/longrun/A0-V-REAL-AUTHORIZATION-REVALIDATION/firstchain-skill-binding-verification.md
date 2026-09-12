# 数据参谋与首链技能绑定

2026-09-12T02:49:43Z，克隆、主库均沿正式 AgentInstanceActivationService 激活 ecommerce.data_advisor.default@2；D01/D02/D03 SkillBinding 各 active@3。其他 D04-D06 无绑定。旧模板和技能内容不改；每技能引用自己的已发布 route/policy/Skill Gate 与实际能力绑定。

技能就绪服务子依赖原先使用默认连接，现与注入连接一致。连接/技能就绪测试 11 passed，精确参谋模板与技能覆盖测试 6 passed。克隆 524 表重放无内容变化，主库 227 AIP 表重放无内容变化、223 租户 AIP 表 canary 内容保持。主库使用紧邻前一步完整备份 firstchain-capability-main-apply.json。

当前 1/6 数字同事 active、3/37 SkillBinding active。生意探究职责模板还要求六角色：owner、data-steward、content-research、customer-research、channel-research、business-reviewer，能力分别是 strategy.plan/material.collect/content.review。不能仅激活数据参谋就强行冻结完整职责计划。下一步补只读探究职责的其余角色真实文本能力及绑定，再正式物化职责计划；媒体和其他业务仍独立验收。
