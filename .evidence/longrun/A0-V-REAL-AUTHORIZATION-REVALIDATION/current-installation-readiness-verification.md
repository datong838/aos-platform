# 当前安装就绪与健康刷新

2026-09-11，基线d521cca0。实际001已升级011，不复用过期schema描述。

栖月汇已有1个安装，历史draft/submitted/approved各1，runtime binding0；不是从零重装。7类配置记录有效，frozen responsibility0。固定只读依赖审计：Provider1、当前health0、active route0，10能力定义及W0b具备，37技能evaluated但无published/logic/eval gate，6agent provisioning，canary各层0。

确认旧health attempt-v2 completed后，为当前健康刷新固定新身份a0v-provider-health-20260911-refresh-1，在独立state目录沿原脚本合同执行（仅当前进程替换ATTEMPT_ID，旧脚本/Journal不改）。一次真实调用成功，373ms/59 total tokens，observedAt=2026-09-11T04:00:56.900507Z，expiresAt=04:15:56.900507Z；观察a0v-health-20260911040056900507；健康记录1→2，canary0，无客户正文或业务写入。随后同配置回读providerCalls0/healthMutation0，证据已完成。不是3/3模型质量验收，过期不能继续声称当前healthy。

本地结果logs/provider-health-refresh-20260911-1.json与同名-replay.json；状态目录.aos-recovery-20260910/state/a0v-real-text-provider-health-refresh-20260911-1，0700/attempt0600，不入Git。没有重复未知请求。

新发现：ModelPriceSnapshotRevision仍明确拒绝deferred active/suspended/revoked；Model发布/Resolver/Invoker已具备当前预算授权交叉校验，用量cost_pending合同及迁移已补，但DTO运行激活仍堵塞。下一波先补可激活及可暂停撤销的开发未核价合同，联合验证Owner/Resolver/Invoker的失效拒绝，再正式发布exact模型路由。保留商业未知价格阻断和真实用量，不再次要求价格。候选安装schema声明仍001需单独兼容验证/新候选，不改旧签名。首链、八场景仍未完成，不push，230 L0挂起。
