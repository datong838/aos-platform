# 分析写入事务内重验领取

基线1ca1c5ce。父任务Host/tests范围。正式处理器不能以之前返回的ClaimedOccurrence对象当当前授权。

在 services/aos-api/aos_api/automation_occurrence_store.py 增加 _lock_claim(conn,scope,claimed)；必须在调用者的同一事务中锁定原Occurrence和dispatch attempt，数据库当前时间校验deadline及claim_until，比较全部领取身份、epoch、目标幂等键和attempt。调用者保留事务、负责后续当前方案/来源/审批复核与提交；本方法不单独提交、不新领取。

services/aos-api/tests/extension_runtime/test_automation_occurrences_pg.py 增加真实PG正确读取、错owner/key/epoch、过期、已接受和跨租户拒绝。原记录不修复不重发。后续在分析处理器提交之前/之后使用本方法；本波仅前置原语，不宣称正式分析接线完成。无主库DDL/数据、重启或push。
