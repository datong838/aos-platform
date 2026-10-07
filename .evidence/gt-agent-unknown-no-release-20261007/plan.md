# AgentRun unknown 不主动释放（完整联合切换的局部修复）

基线 e5bc1999 / AOS-001471，Task gt-agent-unknown-no-release-20261007，唯一m1写者。复习231、产品总纲 unknown必须reconcile与共享物理合同；原transition离开RUNNING的release分支包含UNKNOWN，缺乏外部零效果证明。

精确文件：services/aos-api/aos_api/aip_agent_run_service.py、services/aos-api/tests/aip/test_aip7_agent_run_transition.py、本证据目录。先测试RUNNING→UNKNOWN实际CAS提交后不调用release_for_run，也不新reserve；先取得原代码RED，再仅给原release条件排除UNKNOWN。参数回归PAUSED/SUCCEEDED/FAILED/CANCELLED原release行为，未知CAS冲突零release；原queued启动commit异常语义本波不改，列联合切换后续。

专项运行原transition测试，相邻executor的unknown/replay与ContentCapacityOwner sole-claim不重试、原池单元回归。所有pytest均由现有专属容器与0600passfile启用保留随机隔离库，禁drop数据库。无新增UI，浏览器不适用；正式库/服务/Host/Provider/商城源不操作。

这是状态转换主动释放的局部修复，不证明旧池TTL保留unknown、完整合法创建链PG、两种token额度或共享物理capacity+budget+Intent一次提交。新物理账本必须覆盖这些条件，业务首链及父合同Task仍pending。不能用本unit PASS关闭完整目标。复核改动仅分支条件，其他原方法与正常terminal行为不变；验证后精确提交、Delivery与AOS/Prime同步。

验证：原代码RED 1FAIL/13PASS5.27s；修复专项+executor unknown/replay+Content soleclaim+原池unit 65PASS5.30s/noSKIP，7既有warnings。独立AST比较仅transition release条件变化，其他可执行AST保持原样。两保留bootstrap库原生SER READ ONLY回读AgentRun0/容量0，明确这是unit行为证据而不是合法PG运行链。

另登记gt-agent-unknown-checkpoint-20261007，仅更新 docs/palantier/20_tech/电商平台接入/微商城电商接入方案/D-waves/2026-10-01-W5CB4-BG00gt首次模型评测授权清单.md，记录局部结果及未完成项。父gt-shared-physical-atomic-contract-20261007仍ACTIVE；两个局部Task验证交付后同步权威，不推进业务完成门。
