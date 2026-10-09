# 原完整 description 同 caller 读取必要门复审

先按 implementation-plan.md 登记 Task/Lease，origin-gap-red.json 以已保留库 READ ONLY 确认原风险/描述为0而身份binding=4、无只读 origin 入口、旧 producer 会 INSERT。未将旧 producer 或客户端签名描述当原件。

仅新增 aip_shared_parent_description_origin_reader.py 及对应 PG 测试。显式隔离只读函数固定 pg_catalog、原 physical Owner SECURITY DEFINER、PUBLIC 撤权、runtime 仅 EXECUTE，无直接表 SELECT/INSERT。读原 risk→description，在同 SERIAL native SCRAM caller 比较双租户、xid/pid、canonical 全文/hash/manifest/originalRiskHash 与原事实；包装在前后 Source/Owner 当前性及末尾真实 clock 检查之间。不准备新行、不修复角色、不提交，不变更旧生产者/issuer/迁移/运行入口。

334 项无数据库连接纯验通过（1.21秒）。R1 原件正向、exact replay 与7项负门通过，但后续消费者认证120秒到期且 supplier 清理复核到期，完整节点 FAIL（129.41秒）保留。失败独立回读原风险 ABORTED、四表0、角色均NOLOGIN；occupation password非空是原fixture既有清理行为，不假称清空。

R2 是新的 Source/审批/认证实验：本地 pytest signer包装仅新签发默认300秒认证，显式负门 exp 原值保留，旧JWT/Source/Model请求与独立100秒批准不延长，产品到期校验不改、无mockclock。完整原生节点 PASS（149.93秒）；新认证范围见 native-r2/new-authentication-window.json。包含原两case四leg、实际不同SCRAM连接xid/pid拒绝、管理员不能冒充原调用者、wronghash/bool/canary/fullmanifest漂移/缺原行负门。签名Source与原Suite、母预算、debit/input/Intent及原并发相邻累计一起执行；原实际 deferred COMMIT 拒绝。

independent-readback-r2.json：cluster 7694680278363095064 / aos_test_f9459fd4498b_ti4_test，READ ONLY；原风险 ABORTED、四表0、Source1。原函数 prosrc与当前DDL逐字相同，owner=aos_physical_capacity_occupation_owner、SECURITY DEFINER/fixed path、PUBLIC EXECUTE0、runtime表读写false。全部冻结产品文件hash与当前一致，保护旧实验摘要/未跟踪旧authority和reader原文未变。

本波只收口原件读取必要子门。专属于新 reader 的真实等待跨Source/审批到期与撤回竞争尚未验收，必须继续；原相邻guard竞争不能替代该矩阵。独立issuer事务不能拼成原风险事务，可信root bootstrap谱系、身份/证书同caller只读桥、最终joint/真实token/严格WAL/ACK/Transport/正式首链均待验，executionAllowed=false。Task保持ACTIVE，无整任务Delivery；旧两摘要before-image未恢复，Prime未知请求未重发。无UI改动，浏览器不适用。必要门源码/方案一致；正式安装仍受独立权限和全链验收约束，不能从本实验直接授执行。
