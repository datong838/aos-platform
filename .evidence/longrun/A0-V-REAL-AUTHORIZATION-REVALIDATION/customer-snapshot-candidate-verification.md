# SC4-5e7b CustomerLite公开快照

2026-09-14，基线436e6bb8；Lease A0-V-SC4-CUSTOMER-SNAPSHOT-CANDIDATE。

1.10.0源树d17d81fefde3e8159c1c18b8a361f6bdac128350c1623b9181540d06d57558cb保持；新候选仅bundle/p08/evals相对变化。去掉不存在源列的旧游标，选择member_id/member_level/reg_time/status/site_id/is_delete，原公开白名单核验通过。旧derived指标/关系不在本候选伪造执行。

对象schema2，公开业务属性memberLevel/status/createdAt及强制观察来源标记、规范时区。源status仅已实际观察1通过，其余拒绝不猜测；删除独立is_delete明确0/1。零注册时间拒绝不回填。原手机/OpenID/姓名等保护不变。

先缺生成器红测3 failed；实现后45 passed/7既有警告/5.65s，八类合成规范对象评估通过。AR2 1909/187/93五数组空；diff-check通过。真实只读聚合54名会员均有注册时间，不能代替正式采集/需求补齐；无发布安装或主库写入。

SC4-5e7b：CustomerLite公开schema2候选1.11.0完成，45项回归/八类静态对象通过。仅选原允许六列，未知status拒绝，显式软删与真实注册时间保留；公开业务属性仅等级/状态/注册时间加强制来源标记。新树f2bc7069f564af79dbef3feb14da9ba64a7b6fd767cef4a2879421caf71cb7f5；静态8/12，主库仍先前2/12。下一后四类源字段政策、关系/支付订单关联与真实补齐。
