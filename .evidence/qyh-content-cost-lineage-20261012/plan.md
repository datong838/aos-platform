# 栖月汇内容费用与任务接线核查

Rules：231/原八工作台产品分层、双租户、native有限LOGIN/RR/READ ONLY、Receipt/Lease、先方案、无未知重发。基线aa5d9c0b77bc4680747ce18d8418997ce18736ab / AOS-001901。

已登记候选：一、Content readiness当前费用/Task/AgentRun接线（优先），依赖原审批/价格/预留和实际运行对象；二、受控内容对象Owner接线，依赖真实对象存储；三、既有OIDC/独立publisher配置接入，仍需实际配置来源。当前先对候选一做实际权威读回，不用客户端补值替代。

文件级计划：本目录readback.py/result.json/review.md；不改services或当前数据库。读取已恢复aos_meta_head@159同cluster，原有限factory提供连接，设置RR/RO后scope；显式校验身份、事务和版本。仅聚合各原表数量/状态、AgentRun→TaskRun/Task refs、attempt→AgentRun、费用审批和预留关联存在性；不输出主体、对象数据或凭证。schema字段先只读核查，不猜表名/字段。原647表指纹与metadata前后比较。

验收：明确区分记录存在/当前有效/正式权限；运行状态和审批不能从数量推导。保留当前不可接线原因，费用审批/预留存在也不授Provider；代码允许正常内容新链的最小方案须以本次缺口为依据，不能伪造Task或运行旧12Run。无页面改动，本波不声明浏览器/八工作台验收。
