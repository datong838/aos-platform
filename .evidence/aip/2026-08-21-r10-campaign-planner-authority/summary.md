# R10 活动策划师 A01～A06 权威闭环 EvidencePack

结论：`GREEN_WITH_UI_WARNING`。运行权威与安全边界 GREEN；目录统计口径存在一个后续 UI 修复项。

## 真实运行事实

- 正向租户固定为 `org-org/dev-project`；浏览器顶部回读为“栖月汇商贸有限公司 / 默认工作区”。
- 活动策划师唯一实例为 `active`；A01～A06 共 `6/6` published Skill、`6/6` active SkillBinding，浏览器目录为 `runnable`。
- A01/A03/A04/A05/A06 均有独立 Logic revision、隔离 Eval、成功 dry-run 与不可变 LogicPublication；A02 exact Graph/Skill/Binding/Pilot 历史未改写、未重放。
- 新鲜度来自 separately-approved Agnes text `3/3` Health：`health-agnes-text-qyh-r2-20260821070802980631`，有效期至 `2026-08-21T07:23:02.980631Z`。到期后目录必须诚实回到 stale/blocked。

## 安全边界

- 本波未创建 AgentRun，未执行活动业务 Provider call，未发券、改价、投放、上架、群发、改库存、启动实验、暂停线上活动或写入长期记忆。
- 五条新增 Logic 只产生内部 Draft；超预算、毛利不足、库存/履约事实过期、assignment 未冻结、止损触发未暂停、样本不足等条件均在外部动作前失败关闭。
- A02 仅复用 immutable authority；对应五个源文件 SHA-256 与 pre-hash 完全一致。
- `dev-org/dev-project` 仅作负向 canary，CapabilityBinding/SkillBinding/AgentRun 增量均为 0。

## 验证

- R10 targeted：`37 passed`。
- R06～R10 累计：`219 passed`。
- `compileall`：GREEN。
- 内置浏览器：活动策划师 `6/6`、目录可派发、`runnable`；工具箱明确只读 Overlay，不伪造已启用数量；控制台错误 0。
- UI 警告：目录卡片显示“专业能力 14/3”，分子为绑定展开量、分母为能力类数量，口径不可比较；登记为 `R15_AGENT_REGISTRY_CAPABILITY_COUNT_SEMANTICS`，最终 UI 封板前必须统一为同口径统计。

## 提交与所有权

- Logic 安全契约：`1808437`。
- Logic authority：`20594eb`。
- Skill authority：`cde7917`。
- Binding composition：`b6580b4`。
- runtime tail：`1074f0c`。
- Workshop B5 只能由 m1 串行 CAS 消费；canonical SourceReadiness owner/API 与同 cutoff 12-source EvidencePack 只能由 Data/Adapter owner 交付。w1-aip 不复制第二权威。
