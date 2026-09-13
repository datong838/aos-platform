# BG-02 当前安装候选发现

基线3d1adf5c。新增ecommerce_product_event_discovery.py：显式TenantScope+安装/generation；查询当前event policy head与同版本/hash enabled/approved binding、精确SourceSelection引用、同安装管线原Claim、已succeeded且stopped的run、原parent/derived/dataset receipt存在性、该run schedule的最新control binding（含同actor）。只返回policyId/runId/actor/current controlRef和字典序扫描key；不返回载荷/源配置/密钥，不视为授权，消费Owner仍全重验。

每页1..100，after=(policyId,runId)只用于轮转，末页后重置到开头；不能持久化为最大事件序号或消费ACK。迟提交较小key在下一轮可见；失败和空候选也推进本轮扫描，避免前缀饥饿。目录目标/页数限制由后继worker调度。当前窗口外不选择新执行，已经入Occurrence的超时仍走原missed机制。

测试真实临时PG最小关系验证租户/安装/generation、最新控制续期、disabled/未完成排除、两页及回绕后迟插入。测试SQL不是完整当前授权证明。文件services/aos-api/aos_api/ecommerce_product_event_discovery.py及tests/extension_runtime/test_product_event_discovery_pg.py。无DDL迁移/业务写入/主库/worker启动。
