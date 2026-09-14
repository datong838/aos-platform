### SC4-5l6d2 严格完整快照就绪策略编译

基线a0d9d9e4；新增pipeline_snapshot_readiness_policy.py和对应tests。原FactQualityPolicy与SnapshotRelationshipQualityPolicy精确类型/hash/purpose绑定，完整有序P01-P12且原field facts唯一全覆盖；固定requirement-oldest-observation/current-original-base-and-derived，显式规范queryBindingId。输出冻结tuple/dataclass和规范hash，没有ready字段；策略名称不等于数据库绑定存在或授权。

Red为新增模块缺失；23新增+25原field+14原business共62 pure passed/5.64秒、7既有warnings。实际冻结1.21的12类策略经原编译器输入，覆盖缺失/重复/顺序/错误ProductReview名称、额外字段、模式/purpose/hash/空或非法binding及原输入不完整等拒绝。AR2扫描1943/190分类/93迁移五类错误空；memory strong CURRENT/validate GREEN。无DB/源/模型/主环境动作，非真实ready验证。

下一波SC4-5l6d3：准备Niushop 1.22.0候选，源1.21冻结tree hash，新增content/policies/snapshot-readiness.v1.json及版本/静态eval。原文件逐字节保持，原已有queryBindingId配置仅作显式策略选择，真实当前绑定在d4核验；不build/sign/install/publish。随后d4当前事实、d5原就绪计算、d6原Receipt，原恢复/Outbox/真实业务闭环任务继续。m1、不push、230 L0挂起。
