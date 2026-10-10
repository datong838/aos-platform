# 完整准备写入/安装对账复审

原14个生成器的静态SQL原件（不执行DDL）和R22 retained真实pg_proc/pg_class分别对账。r1因零参数trigger函数在提取器被当成有参形状拒绝，断言发生在数据库连接之前，0数据库操作；保留r1及失败记录，r2只允许明确空参数列表后完成只读核对。未知形状仍拒绝。

原数据库确缺prepared_judge_intent、prepared_call_occupation、call_occupation、call_occupation_event四表。实际15个public source/prepare函数当前缺席；复核原test finally明确DROP Source/guard/eval/case/input/Intent/Judge前缀，故不能将这些terminal fixture cleanup缺席解释为产品实现缺陷或此前native节点没执行。R22 trial prefix确只安装Judge fact/debit、planrisk、description及新signature/reader工件，未安装四表后继生成器。独立保存旧R22结果和前安装hash，不补DDL或重发旧risk。

源码完整准备写入链明确：account guard I/U；两个budget hold已知bucket/reservation/link；Target parent_guard I/U+parentdebit I→case/input binding I→Target Intent I；Judge parent_guard I/U+parentdebit I→Judge Intent I（仍awaiting_target_result）；planrisk I→shared description I；cert/Manifest/epoch/identity staging；Target prepared_call I→occupation root I→initial event I。因此后继候选应至少将缺四表INSERT纳入，22旧已知事件变为26准备候选；此是人工可见SQL上界，不证明动态/间接/实际queue闭包，也不等同full execution writer inventory。

完整执行缺口仍实质存在：prepared_call schema虽允许target/judge，当前实际producer只有Target；ledger只允许target及prepared_only/counts_as_inflight=false。Judge Intent awaiting_target_result不能充作Judge输入/已执行/Usage，不能为了finalizer整齐给Judge插假call或已完成结果。必须沿真实Target结果→Judge输入协议补合法后继，完整结束/结算/wait-currentness仍待开发。正式Root/WAL/HostProvider门不变。

下一同Task10原生矩阵具体入口：fresh独立保留库，新Source/审批/Root/签名原件，安装全部四表生成器并冻结function/table/constraint/Owner/ACL。先真实同caller Target Intent→prepared call→ledger initial、Judge awaiting intent完整准备正向与逐边界负门；保留全部original deny，actualCOMMIT拒绝和全新写表/metadata回滚独立回读。采用原ledger trial创建接口和原native certificate prepare接口组合，不能复用R22撤回原件、不能用单个旧fixture通过冒充组合。外部Provider0，fullGoal/Task9/10不Delivery。浏览器不适用于本隔离矩阵。
