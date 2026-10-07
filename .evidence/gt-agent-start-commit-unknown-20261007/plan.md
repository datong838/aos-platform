# 启动 COMMIT 结果未明时不释放容量

基线60480bcc/AOS-001472。已复习231、产品总纲unknown必须reconcile及父共享物理联合合同。原transition先reserve容量，再AgentRun CAS和COMMIT；COMMIT异常不能证明AgentRun提交失败，却会主动release预留。修复后保留预留，原异常抛回，由Owner保持claimed和只读对账；禁止重发。已知CAS未匹配的原清理路径不变。

具体文件 services/aos-api/aos_api/aip_agent_run_service.py、services/aos-api/tests/aip/test_aip7_agent_run_transition.py和本目录。测试先将原commit失败期望从release改为保留；加提交已成功但响应丢失的连接，证明在服务端已commit时也不能release。两例RED后仅把commit异常分支的release调用改为保留告警；测试精确原异常身份、只reserve一次、无重试、无release，CAS失败和其他终态行为回归。

测试运行器使用已有专属PG容器和0600passfile，所有随机bootstrap库保留；专项+executor unknown/replay、ContentCapacityOwner未知claim不重发、原池unit相邻。无UI变动，浏览器不适用；正式库/服务/Host/worker/Provider/商城源不操作。AST对比除commit异常处理外的代码保持；日志仅标识AgentRun/预留，不记录原异常文本或凭证。

限制：这是服务单元测试，不声称真实PG网络COMMIT丢包或合法AgentRun完整创建链；保守保留可能暂时占用旧池额度，后续须结果Receipt对账。旧池TTL仍会回收，此修改不等于unknown物理义务保留完整实现。父合同要求两种token模式、signed Source/旧义务/普通Eval/预算/一次Intent完整caller真实提交，均保留pending。

结果：原代码2FAIL13PASS5.61s，恰为提交前异常和提交后响应丢失；修复66PASS5.20s/noSKIP/7既有warnings。独立AST把新静态warning还原原release后整文件完全相同，其他行为未改。原生SER READ ONLY检查两个保留完整迁移bootstrap库AgentRun0/capacity0，不称合法PG链。

另登记gt-start-commit-unknown-checkpoint-20261007，范围仅外部workspace D-waves/2026-10-01-W5CB4-BG00gt首次模型评测授权清单.md，记录此结果和后续完整联合合同；该文档在aos-platform Git之外，用SHA256绑定Delivery，不混入其他repo提交。
