# W5CB4 BG-00e｜D01 正式 Skill Eval 来源审计方案

按 231 首链、AIP-4 E1A/E1B/E1C 和 AIP-6 A6E，先只读锁定当前首段 D01 evaluated 修订，再查当前租户 canonical Dataset→Suite→Run→Report→Gate→Event 精确生产链。旧 `/v1/evals/*` 是 Logic compatibility，37 条 evaluated 是定义发布初态，不表示已跑正式评测。任何正向 Suite/Report 必须有真实来源 hash、脱敏 Receipt、Case Artifact、Judge exact revision、正式执行器和 Actor 权限；本波不得创建空壳、合成样例或读取商城源。

文件级动作：只读 `aip_skill_template_revision` 与七张 AIP-4/Skill 目标表；核对 `AipEvalPackRegistry`、`AipEvalRunner` 和现有 Router/产品页；写 verification 与 D-waves。若 Dataset/Case/Judge/执行器仍缺，D01 实例保持 blocked，并把可独立实施的 SkillBinding 产品页面流程列入 BG-00f。后续盘点确认 `/v1/aip/skill-bindings` 的 create/preview/evaluate/activate API 已存在；须复用现有 Store 的 published-only、exact tenant、幂等 Receipt 约束，不添加平行路由或高权限捷径。
