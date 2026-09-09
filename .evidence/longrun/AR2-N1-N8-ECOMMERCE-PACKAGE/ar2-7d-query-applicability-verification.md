# AR2-7D D1 Requirement/Query 适用性验证

2026-09-09，基线575c5e7e；m1单人施工，不push，230 L0挂起。

- 新适用性、既有DataRequirement Store及固定商品Query三文件37 passed，8.57秒，/tmp/ar2-query-applicability-green.log；仅18434本次自有一次性数据库。首次23 passed/2 failed为夹具错误：canary实际抛DataRequirementNotFound；已经执行查询的事务不能再SET isolation，改为普通连接。未弱化实现门槛。
- 实测全三字段匹配仍not_applicable；窗口/截止/过期/取消/未来创建/输出缺口；选择漂移、观察撤销、canary拒绝、普通隔离拒绝；仅SELECT/SHOW、不重复比较、临时需求表不能隐藏public、外层回滚移除新需求和Query。旧需求原JSON false→0回读拒绝。
- 本地独立只读审查无阻断项；非外部Prime。诊断SHA-256 a099328928d88bfa1bb968e74a4bde80f7855becf43ed3b2079475b637becb9c；Requirement Store eb1ac030ed3fb166a540cedda56a4470344d417691c68688bde997f5fe38f58a。
- 旧需求写入JSON格式/内容hash保持，get_exact新增原JSON摘要和严格ref/public限定。诊断仅针对指定历史修订，不查当前头、不产生当前准入或履约权威。方案与实现一致。
- 闭包ar2-1扫描1702/分类88/迁移57，五类错误空；diff --check通过。AR2-7D仍未完成，AOS-000571不前推。
- 下一项补实际Product观察字段和联合有效测量所需的保真输入。既有v1清洗会剔除部分坏行、且无category_id/goods_state，不能作为完整Product质量分母。须显式新spec保留范围内坏行，不改历史v1语义，更不能由归一化默认值制造真实字段。
