# 原始 Source 期限与重复核验耗时调查

Rules：231、原联合方案第3/11.3节、AOS工程交付Skill；m1唯一写者；真库只读，所有调查仅指定隔离库；不得延长期限、改审批、复用旧调用或削减等待后的原权威复核。

已登记候选：
1. 当前live-physical WIP的原链耗时调查：当前Task已授权，依赖原始timings与保留隔离库；本轮执行只读原canonical函数测量和静态调用层级复核，优先。
2. 全终结风险账本/唯一请求对/事件与RI顺序：同Task已登记；依赖原文合同与后等待全权威核验、当前物理union门正向及超量负向证据；不以WIP推进正式部署。

具体文件：本计划与 source-timing-investigation-1737.json，仅位于当前Task .evidence目录；不修改产品代码、旧SQL体或任何审批/Source原件。

只读原库 aos_test_7efed020dfe1_ti4_test，精确cluster7694680278363095064；SERIALIZABLE READ ONLY，查询原canonical函数元数据及保留真实签名Source的canonical哈希/字节一致性、计时。jit on/off仅SET LOCAL，用于排障，不能据此更改生产设置。记录Source长度/hash与时间，不输出正文、凭证或密钥。已有旧attempt只读对账，不重放业务操作。

验收：现有timings必须逐条复核，尤其Window已返回，首次live读才因Source过期拒绝；对比1735/1736真实同名调用时间。简单manifest测量不能证明Source完整核验性能，重复嵌套是候选原因而非已证根因。下一轮只允许根据证据设计具体安全优化，保留原算法、锁序与期限。
