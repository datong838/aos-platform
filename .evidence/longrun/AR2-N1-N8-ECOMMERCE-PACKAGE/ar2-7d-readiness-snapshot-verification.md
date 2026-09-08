# AR2-7D D1 SourceReadiness 快照原语

2026-09-08；第3/8步，同父任务AR2-HOST-WIRING-CUTOVER-PLUGGABILITY-BROWSER-ACCEPTANCE。

新增公共SourceReadinessReceiptStore与ar2_009，保存既有Owner计算结果，不另造就绪判断。
全部嵌套时间统一UTC与固定微秒；正文receiptRef=null消除自引用；tenant+正文hash内容寻址，
公开ExactResourceRef与InvestigationExactRef的版本/hash格式边界已记入231-6。
仅HostTransaction，无独立commit、API、已启用port或外部操作。

专项及相邻合同测试：test_source_readiness_receipt_store.py、test_source_readiness_contracts.py、
test_source_readiness_investigation_projection.py，共10 passed /11.70s。
覆盖隔离PG并发去重、typed精确回读、双租户隔离、主事务回滚、不可变权限、错hash/身份/状态反例。
独立Prime设计与代码只读复审通过，所提深层非法快照反例已补入本次验证。

明确边界：SQL只验核心形状、原文hash、租户及P01～P12聚合，不重复完整Python业务DTO。
运行角色直调产生的独立非法深层正文不能通过typed读取，不占合法正文地址；测试同时证明
合法原快照仍可重放。业务禁止绕过typed Store直接依据SQL status授权。

下一切片：真实Requirement/Hydration/Evidence构造investigation投影与DataFulfill绑定。
现有SourceReadinessService尚不产生该投影，本原语不等于履约已完成。
仅隔离库迁移；未迁移共享数据库、未调用Provider、未修改真实业务数据、未新增页面验收结论。
