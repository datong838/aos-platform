# SC4-3a 启动门原事件事务绑定

基线bd051b4c，m1父Lease内修改AipProductionStartService。新增可选connect_factory，默认保持原connect；默认Contract/Action/Task Store复用同factory，start/get/list都由其打开连接。支持原事件Host的TransactionBoundConnectFactory，不改变任何Plan/Preview/Context/Action审批/Logic门禁，不直接绕过组合启动服务。

RED：新增测试因构造不接受connect_factory失败。GREEN：原test_w2d_start_gate.py及真实分析编译PG累计9 passed（6.22s）。新增实际门禁通过→创建TaskRun→同事务get/list和同key重放→外层故障，确认StartDecision/TaskRun/Plan批准状态/Task状态版本全部回滚。原未批准、Logic错误等拒绝仍通过。

测试沿用原W2-D隔离候选fixture（legacy测试租户），不是主安装真实经营执行；后者仍只认org-org/dev-project。SC4-2上下文编译PG也通过。AR2 1899/177/93无错误，git diff --check通过。尚未创建主安装TaskRun，正式START严格xfail保留。

下一SC4-3b：当前分析启动ImpactPreview及审批依据的自然承接，继而AIP运行/暂停和sealed Host。当前安装允许触发分析不应伪装成某个人已经批准本次经营方案；启动与经营exact评审分别记录。无push、230 L0挂起。
