# 完整 Source catalog profile 实施计划

Rules：仓库 AGENTS、231 八步、联合准入完整 §3/§11.3、aos-engineering-delivery、单写/真库只读/未知效果先对账。authority AOS-001763；三个原依赖 Task 已以相同 owner 核对 Task=Lease、未 Delivery 后正式续租，不凭 TTL 删除；新 Task 仅占新增模块、测试及自己的证据范围。保留 publication_transaction 原有工作树 selector diff 为 beforeimage，不覆盖。

已登记候选一：完整 fixed catalog profile 编译/身份识别，授权为隔离实现，依赖原三锁 profile 与 Source/occupation Task；本轮首个安全步骤。候选二：签名 Source 下 Receipt v2、最终物理比较、原生末门与 actual COMMIT 矩阵，依赖候选一及 Source 时限，不能用 helper 或测试拥有行替代。

新增文件 services/aos-api/aos_api/aip_provider_capacity_catalog_audit_profile.py、services/aos-api/tests/aip/test_provider_capacity_catalog_audit_profile_pg.py。原合法 Task 下最小接线文件：aip_provider_capacity_occupation_epoch_profile.py、aip_provider_capacity_occupation_source.py、aip_provider_capacity_publication_transaction.py（均位于 services/aos-api/aos_api/）。旧 SQL/migration/trigger/默认生成器逐字保留。

固定编译仅替换两个列权限谓词，保留原角色/表权限/默认 ACL/RLS/策略/守卫/当前原事实审计。新 FACT 摘要绑定完整 private audit，新 private 摘要绑定全部 public 与 occupation Auditor。无调用者 SQL/hash overrides，无目标目录派生 trust，无自动安装。原生识别仅精确 body、Owner、语言、metadata、ACL 及完整三锁身份；混合/部分/ACL漂移拒绝，不能回落旧身份。

先缺模块 RED，再编译校验与 native 隔离 transaction rollback 正负门，独立连接恢复复核；相邻测试复核原生成器 hashes。完整签名 Source 时限/消费、Receipt 与实际 COMMIT 后续实际验证，当前不写 Delivery。浏览器无页面改动，不作为此组件门。失败保留证据，rollback 测试更改；正式安装/Root/Provider/全局角色均不操作。

观察器本 heartbeat 返回既有事件缓存（HEAD18093f、authority1703、Judge checkpoint），与当前 HEAD2ef3e96/authority1763 不一致；仅保留历史观察结果，不能当当前任务进展或授权。
