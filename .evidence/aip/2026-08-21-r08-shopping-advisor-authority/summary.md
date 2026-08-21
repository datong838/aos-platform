# R08 导购顾问 G01～G06 权威闭环 EvidencePack

结论：`GREEN`。

## 真实运行事实

- 正向租户固定为 `org-org/dev-project`；浏览器顶部回读为“栖月汇商贸有限公司 / 默认工作区”。
- 导购顾问唯一实例为 `active`；G01～G06 共 `6/6` published Skill、`6/6` active SkillBinding。
- 浏览器截止点 `2026-08-21T05:25:32Z`，导购顾问为 `runnable` 且 blockers 为空。
- G01/G02/G03/G05/G06 均有独立 Logic revision、隔离 Eval、成功 dry-run、不可变 LogicPublication；G04 exact Graph/Skill/Binding 未改写。
- 业务命名已统一为：需求诊断、产品检索与推荐、成分分析、产品对比、异议识别与处理、促单与成交交接；稳定 ID 仍为 G01～G06。
- 新鲜度来自 separately-approved Agnes text `3/3` Health：`health-agnes-text-qyh-r2-20260821052056435534`，有效期至 `2026-08-21T05:35:56.435534Z`。该快照到期后目录必须诚实回到 stale/blocked，不能把历史 GREEN 当持续可派发。

## 安全边界

- 本波未创建 AgentRun，未调用业务 Provider，未发送推荐，未产生订单或其他生产 Action。
- Logic 只生成 Draft；G06 要求 exact 人工/订单结果引用和受控流失原因，不提供生产旁路。
- Product/SKU/Price/Inventory/approved knowledge 均使用 exact 引用，库存必须新鲜、价格必须一致；原始个人信息和 Secret payload 不进入 Graph/Skill/Evidence。
- `dev-org/dev-project` 仅作负向 canary，CapabilityBinding/SkillBinding/AgentRun 增量均为 0。

## 验证

- runtime targeted：`10 passed`。
- R06+R07+R08 累计：`141 passed`。
- `compileall`：GREEN。
- 内置浏览器：智能体目录显示导购顾问 `6/6` published/active、`runnable`；展开后六项中文技能完整；G01/G06 逻辑画布回读 canonical hash 与发布历史；G06 显示生产旁路关闭、自动化禁用；控制台错误 0。
- AIP 跨页总真相仍只显示 `1/6` 可派发，这是其他角色新鲜度尚未刷新，不冒充全平台 GREEN，也不影响 R08 exact cutoff 结论。

## 提交与所有权

- Logic 安全契约：`6ff7348`。
- Logic authority：`d958179`。
- Skill authority：`fa82a7f`。
- Binding composition：`420ebc9`。
- runtime tail：`1a0b244`。
- P08 与 AIP `DEP-ADP(query)` 已关闭；SourceReadiness/同 cutoff canonical EvidencePack 归 Data/Adapter owner；Workshop B5 归 m1 串行 CAS owner，均不由 w1-aip 越权代做。
