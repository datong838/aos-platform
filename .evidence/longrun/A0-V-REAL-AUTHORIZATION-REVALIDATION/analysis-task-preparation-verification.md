# CF3-3 Task与意图简报准备验证

基线b656a306。prepare_analysis_task为Host内部辅助，验证Case/Run/状态hash/租户与L1意图后，用稳定Run key创建Task，v2简报正文与Task.goal相同；复用原创建/冻结回执，内层不能提交。当前Task意图/状态或Brief头漂移拒绝，不创建替代任务。

Red缺模块4 failed；首轮真实PG发现HostTransaction没有公开connection属性，修为直接使用受限transaction.execute接口。Green Task/Brief4+v2意图5=9 passed；追加实际回执计数4 passed。隔离18432临时库读到一个Task、两条Brief修订和两条Receipt；重复准备相同，外层回滚无Task残留。Case/Run是明确合同fixture，非主库真实权威；调用者必须持当前claim及SourceOwner边界。AR2登记新Host调用方后1895/173/93所有错误为空；memory validate GREEN/AOS-000573；diff --check通过。

下一波CF3-4追溯真实EvidenceBundle/Eval来源并冻结本次ProductionContext，之后正式CompileSaga；CF4真实START尚未通过。无主库写入/部署/push，230 L0挂起。
