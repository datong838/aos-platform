# AR2-7D D1 联合计量 QueryResult 验证

2026-09-09，基线9c4fc15f；m1串行、不push、230 L0挂起，测试仅自有18434一次性库，无真实源/Provider/发布。

- 新Query、旧Query、联合计量与旧Metric Store四文件最终50 passed，5.86秒，/tmp/ar2-joint-quality-query-final.log。覆盖实际两个Owner、同事务回滚、重放不再计量、并发旧SERIALIZABLE冲突后新事务reconcile、输入/actor/selection漂移、canary、撤销、0人口和0区间拒绝、固定规则变更、严格计数。
- 首测18pass/1fail为测试尝试关闭触发器被runtime非owner权限拒绝；未放宽权限，改为已有惯例的只读返回正文注入。原JSON revision:true通过正文摘要拒绝，额外计数注入通过固定合同拒绝。
- 独立复核发现joint还需要交集下界。单行八组均有效、joint=0反例先DIDNOTRAISE（/tmp/ar2-joint-quality-query-intersection-red.log），再补joint>=max(0,sum(fieldValid)-7*eligible)后通过；该边界不重建实际AND。
- 本地独立终审无阻断项，非外部Prime。新Query SHA-256 9fcb6377e1b18832329ce3534bcadef745ad48b171370375269c6cdfd32c1bba；共用Metric helper 6bf66a19eadf6ba75d4533fefff8b89633e1b489de5b958397f4a675291cfad2；旧Query仅提取_metric后d499e75d881f1005010daade84b819c6b40e152cfed08d7cb952942f499f41e8。
- 旧定义、hash算法、actor/public Owner行为保持；通用Metric Store未修改且原自定义schema测试通过。新Query.createdAt采用实际测量时刻，deadline内写入，flags固定partial/unknown，不把QueryJob计算成功当经营质量通过。
- 闭包ar2-1扫描1705/分类91/迁移57，五类错误空；diff --check通过。方案实现一致，AOS-000571不前推。尚缺完整规范版本关联、Requirement事实/人口策略、DataFulfill及D2-D4/7E。
