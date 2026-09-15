# SC4-5l6m 当前审批版本协议核对

Rules：m1 串行、先方案、最小修复、隔离数据库，主库与真实审批不变、不 push，230 L0 挂起。

基线 dfbc2d99。标准临时数据库 ProductEvent current/control approval PG 两文件已跑通 21 passed，但 fixture 直接写 proposal.version=approval.proposal_version=1。真实 AipActionStore.decide 先保存当前 proposal_version，再将 proposal.version+1；多审批人每次继续推进。因此旧门禁要求所有 event.proposal_version 等于当前 proposal.version 的判断与真实 writer 不一致，不能用上述绿测认定生产可用。

先验证生产 writer 本身：用隔离 PG 中的 drafted Proposal 调用真实 decide，回读 proposal/event 版本，保留真实 guard、写入和输出模型；测试连接适配器只让内部 commit 留在 fixture 外层回滚中，不替代 SQL 或资格判断。再让当前 event 门禁消费这些真实生成行。新增 tests/extension_runtime/test_product_event_approval_writer_pg.py。

修复方向：当前已批准方案需要一条连续的批准事件版本链，最后事件版本+1等于当前方案版本；内容 hash、action binding、policy、actor、期限、maker-checker 的现有校验仍须成立。不能简单接受任意较旧 approval。原 schedule Host 的二次检查也需对齐；先定位并登记文件范围后修改。

本项未完成前不部署新版本；完整 Service 签名/审批集成仍为后续门禁。

实际 writer 红测已确认：proposal.version=2、event.proposal_version=1，current gate 报 current approval set binding differs。实施范围：ecommerce_product_event_approval.py 用所有批准事件的唯一连续版本序列验证当前方案 version；ecommerce_product_event_host_service.py 的单事件前置检查只要求其版本早于当前方案，最终完整版本链仍由公共门禁校验。同步 test_product_event_host_service.py 的 fixture 到真实 writer 语义，原版本漂移用回退到 1 触发；新增 writer 单人/双人批准与跳跃拒绝测试。
