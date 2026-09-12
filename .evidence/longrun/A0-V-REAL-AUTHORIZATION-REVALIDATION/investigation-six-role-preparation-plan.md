# 生意探究六角色就绪实施

目标是现有产品职责模板的六个只读探究角色就绪，而非一次开启全部经营技能。现数据参谋 D01-D03 active。

补齐原角色已有技能：客服 S01（material.collect）、私域 P01（material.collect）、内容 C06（content.review）、投放 A02（strategy.plan）、导购 G06（strategy.plan）。这些技能从各自角色模板来源发表，不把数据参谋技能硬接到其他角色。沿现有角色 graph builder、隔离 contract evaluator、Eval Registry/Runner、Release、SkillPublication 发布；隔离合同通过不代表真实业务内容合格。五角色只能在对应 exact 能力及技能绑定成立后参与计划。

施工：scripts/aip/bootstrap_r07/r08/r09/r10/r11_*_skill_authority.py 的 _skill_eval 增加可选 connect_factory/actor 参数，默认旧行为不变。scripts/a0v_firstchain_skill_publication.py 扩展显式受限五 ID 支持，保留原 D01-D03 默认入口；新增 scripts/a0v_investigation_roles_materialize.py 固定五 ID，克隆先行主库后行。之后各角色 exact EvalContract、独立五技能内部用途 EvidenceBundle、CapabilityBinding、AgentInstance、SkillBinding。扩展后的证据选取必须按 exact subject 集合区分原三技能 Bundle，不能混用不同授权证据。

不改原模板责任分工，不缩减六角色的职责计划门槛。主库仅正向租户，canary 内容前后摘要核对，重放需无新增或内容改变。230 L0 不纳入本波。

克隆推进至前三项后，A02 被通用 campaign builder 拒绝：A02 使用既有独立 aip_a02_pilot 合同。改由该专用 builder/evaluator 及 bootstrap_r2_a02_skill_authority 可注入连接执行，不退回通用模板；前三项已发表状态保留并幂等接续。

五技能许可第一轮已建立治理任务并领取租约，但领取后复核仍使用原三技能参数，因此在写事实前被拒绝。修复将 exact 集合复核提前至领取之前，verifiedInternalLicenseCount 使用真实集合长度。对已由同一固定 worker 领取且仍有效的租约，通过 heartbeat_step Owner 返回原 fence 接续；不是新领取或覆盖租约。外部 worker 的有效租约继续拒绝。保留原 Task/Run，不重复造治理任务。
