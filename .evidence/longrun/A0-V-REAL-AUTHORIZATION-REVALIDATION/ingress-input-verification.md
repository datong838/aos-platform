# 规范恢复输入验证

2026-09-11，基线b0968513，A0V-INGRESS-INPUT-20260911。

IngressJournal可选output_rows随原envelope同一INSERT保存；原hash覆盖规范输入。仅保留writer/派生所需字段，datetime/Decimal固定JSON表示，未知值/非有限数字拒绝。重建基础对象/关系与原命令逐项一致才接受。旧envelope兼容；未修改实际executor，未新增DDL。

先新增测试确认缺少实现失败；实现后组合14通过（PG Journal3、规范输入4、SQLite恢复7）。PG第三项扩展验证规范outputRows跨连接回读、改变order_count发生同run冲突；其余原租户隔离/不可变/父派生命令验证保留。纯测试确认前后prepare派生命令一致、规范时间、辅助字段、不复制原始无用/凭据名列、基础漂移、非法值。diff-check通过。PG位于colima-aos-extension/aos-a0v-recovery-pg隔离schema，未写public或真实上游。

限制：规范快照不含Dataset原raw全部列；尚未接实际初始化/claim工作器；旧缺outputRows记录不具备此恢复输入。精确input_revision归属、全投影与Dataset接续未完成，完整真实首链/八工作台未完成。API未重载，不push，230 L0挂起。
