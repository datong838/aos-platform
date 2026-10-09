# 命令变异：本轮后续实际代码调查

1619维护及1620跨caller完整原生已交付。两个已登记候选：①原command model_copy边界（atomic/typed既有授权，依当前Source、原caller/原SQL）；②actual admission/费用/Judge真实输入（依单腿费用risk和Target真实结果，尚未满足）。先①，不改产品。

实际复查：严格包装先要求ProviderCapacityConsumptionCommand实例，再对model_dump(mode=python,by_alias=True)重验证；原Source consumer也重验证同一类型，之后原packet及Source exactref复核。原command要求schema1、org-org/dev-project、ProviderCapacitySourceRevision且revision1，带SecretStr；未知字段的model_copy与序列化之间是否丢弃尚未真实验收，不能仅以extra forbid推断通过。

下一新增隔离测试目录 .evidence/gt-wrapper-command-mutations-native-20261009；保留原完整manifest及真实同caller已安装Source。每次savepoint原command副本分别：tenant.canary、SourceRef.asset_type错、asset_id错、revision严格类型错、content_hash错、未知字段。不得输出bearer或伪造Source；错误只记标签/拒绝类型，不打印对象/异常原文；每一项后原typed重放和同callerxid/pid不变。旧十项不重复，原审批50秒不扩；若未知字段被序列化省掉，如实登记规范拒绝缺口，不把忽略额外字段当越权已发生。任何产品修复先独立补方案与原文件Scope/Lease对账。

本调查没有数据库写入/Provider调用/Goal更改；不是下一原生矩阵完成。
