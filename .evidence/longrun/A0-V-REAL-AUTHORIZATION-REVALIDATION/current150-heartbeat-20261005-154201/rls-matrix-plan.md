# 恢复库租户读取矩阵
Rules：231/AOS工程交付、原restore Task、m1单写。候选恢复RLS作用域矩阵及publication签名设计，选首项。固定隔离恢复库只读事务SET LOCAL ROLE，evaluator53 scoped+3 Action表、issuer10 scoped+3 Action表，正向org-org/dev-project对照，错组织dev-org、错工作区、两项空值三负向全count0。空正向表明确未覆盖真实行隔离，不把空表count0报强通过；正向至少membership实际非空。不插入fixture、不LOGIN、不业务写入，role级结果不冒充native完整审批消费。
证据仅本目录rls-matrix-plan.md/rls-matrix-verification.json，完整count私有aos-recovery/current150-.../rls-matrix-20261006-0830.json。仍需原生完整运行/并发和当前库独立迁移安全门。
