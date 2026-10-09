# 原生占用准备响应的严格类型合同

复习231、AOS-001616和next-step-design。两个已登记候选：①严格准备类型契约，依原生root/event及原canonical_hash；②真实准入/Judge结果链，依单腿风险和可信结果，不补造输入。先①。

唯一产品改动 services/aos-api/aos_api/aip_physical_capacity_occupation_contracts.py，原PhysicalAccountGuardPreparation保持。追加root/event/positiveTenant/top preparation DTO。沿用_ModelExecutionContract的未知字段拒绝与实例重新验证；UUID文本和prefixed64hash严格；正向固定租户/原NOLOGIN调用身份；prepared_only，真正bool false，event_seq真正int1/previousnull。顶层call/hash与root/event身份及原事务绑定精确相符；使用原canonical_hash核对两原生contentHash，不复制权威算法。此解析仅描述prepare事实，无授权。

测试目录 .evidence/gt-occupation-preparation-types-20261009/test_preparation_types.py，用已封存原生ledger-green的真实返回值做正向，与其副本中布尔/状态/数量/租户/UUID/未知字段/哈希/跨调用跨事务等篡改负向。先缺类RED，再最小实现，专项和原318相邻累计。没有库操作，不需浏览器；未接SQL运行包装或默认迁移。必须记录原product前缀hash和对应原生fixturehash。

后续单独接原SQL包装与全原生验证，不在本轮声称具备运行入口、actual admission、unknown lifecycle、费用/Usage或业务首链。
