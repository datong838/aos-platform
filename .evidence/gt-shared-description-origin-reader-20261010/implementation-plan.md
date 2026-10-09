# 原准备态 description 同 caller 必要读取门

Rules：231 八步、已批准 typed/隔离评测主线、唯一 m1 writer、正式库只读、旧域不改、未知外部结果只读对账。基线 4170877f / AOS-001675；上波元数据必要门绿不证明 physical 原件。候选一原 description/risk 同 caller 只读桥（本波优先）；候选二 issuer bootstrap 权威谱系（只能调查，缺正式来源不能虚构）；actual token/joint 依真实输入与严格 WAL/ACK 当前性，保持独立。

计划新增 services/aos-api/aos_api/aip_shared_parent_description_origin_reader.py 与 services/aos-api/tests/aip/test_shared_parent_description_origin_reader_pg.py；Task/Lease 精确登记，不改旧 occupation authority、issuer 或迁移。先以原代码和已保留隔离库只读证明 gap，再编码。不得调用旧 producer 冒充 reader，因为 producer 可 INSERT；也不能将独立 issuer 元数据事务与已 aborted 风险事务拼成原调用者。

拟显式安装窄 SECURITY DEFINER 读取函数，由原 physical Owner 持有，固定 pg_catalog，PUBLIC 撤权，仅 aos_runtime 调用；函数校验真实 session_user=aos_provider_capacity_occupation、原 SERIAL/UTC/readonly-off/origin、双租户、pg_current_xact_id/backend_pid。原 risk 与 prepared_shared_risk_description 全行及完整 canonical hash/manifest/双 parent/caller 必须一致，按原锁顺序风险后描述；缺行、其他事务/连接及 canary 拒绝。函数不写表、不准备、不修复角色、不提交；没有直接表读权限扩大。

Python 包装在原 Source 消费和 Model Owner 当前性校验之间调用窄 reader；末尾重读原 Source/审批和真实时刻/xidpid，不能返回 executionAllowed=true。不把 Python 签名或客户端 full hash 当 DB 行。返回原 typed prepared_description_only，供后继 metadata 同 caller 桥使用；本波不调用独立 issuer-role reader伪称同事务 joint。

验证先缺入口 RED；native 原完整 Source/Suite 两 case 四 leg prepared 行读取、exact replay、客户端重哈希 origin/完整manifest 漂移、另 conn/xid、canary、ACL/只读body与真实等待后时刻/currentSource。使用保留独立实验簇，fresh 独立批准，不重放旧过期批准；真实 deferred COMMIT 拒绝并只读核四风险表 0。原 root bootstrap、身份/证书当前门、最终 joint/真实 token/Transport 与自然首链均独立待验。无 UI 改动，浏览器不适用。专项/相邻累计、复审与精确提交后立即接续；Task 不因计划/RED而 Delivery。

R1 原件读取与7反例通过，但完整节点后续原120秒消费者JWT到期，后置 supplier 清理复核同样到期；整轮FAIL保留，原风险ABORTED/四表0，所有实验角色NOLOGIN，occupation原fixture保留非空密码而无membership/LOGIN，不改其清理策略。R2只在新隔离实验/新签发 JWT 默认300秒，显式过期反例changes仍保留，原SourceTTL/原Model请求和100秒独立批准/产品到期门不改；不延旧token、不mockclock。局部pytest fixture signer包装精确记录，旧源码不改。
