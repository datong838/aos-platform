# 稳定产物身份验证

Task A0V-CONTENT-ARTIFACT-IDENTITY，基线da1b5972。AipTaskStore.record_artifact新增可选artifact_id；缺省随机路径不变。显式ID按tenant/id事务锁，已有记录校验run/type/ref/schema/source/evidence/marking/hash/metadata/actor及family/rendition/lineage字段，只有完全匹配才返回原ID，不覆盖内容。

先红：新PG测试失败于unexpected artifact_id keyword。实现后真实隔离PG场景通过（1 passed）：两连接并发同ID只有一行、重放同ID、正文漂移拒绝、缺run和负scope拒绝、缺省接口仍产生不同ID。任务run为隔离最小fixture，artifact结构克隆真实public表，不能作为完整生产schema/业务验收。另现有AgentRunExecutor单测35 passed；diff check通过，既有warnings和JDBC退出logger问题保留。

无public写入/新权限、无真实Provider、无产物上线。下一步结果消费者以invocation派生稳定ID，构造带self ref的电商可读内容，再同事务写Usage、Artifact和费用状态。真实业务内容/来源读取与消费装配尚待完成，整体首链未完成。
