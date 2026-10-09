# 原 v2 Target 持久必要证据读者

Rules：231、共同准入1608与跨阶段1663协议；唯一原 thread/owner，AOS-001664，m1；新原 Task 精确 scope 已登记，无重叠。原产品/技术边界与当前真库不改，Provider off。

精确新增 `services/aos-api/aos_api/aip_model_original_target_result_reader.py`、`services/aos-api/tests/aip/test_model_original_target_result_reader_pg.py`，本 Task evidence。保留既有 untracked reader/authority/migration 原哈希，不夹带其整包提交。复用原 certificate/identity epoch 锁读，不重新复制权威状态机；现有依赖仍由原 typed Task 管理，本波不声称 release package 或完整产品交付。

新必要证据入口为 private Issuer SERIAL 同 caller，无 runtime grant、DDL/角色切换、COMMIT、输入/结果写入或 transport。从原私表读完整 v2 Manifest、v2 Target cert/case、root；重算原 byte/canonical 全 hash、tenant/execution/case/header。按原 root→certificate→identity retained locks 读当前 heads，结果 origin 必须存在、原 positive xid、原 COMMITTED 且区别当前caller；certificate创建时间不晚于 claim.occurredAt，不采用caller checkedAt。读取结束数据库 clock 后重新验 v2 root/cert/case窗口和 Ed25519，原 wire/output byte hash 必须精确；boolean epochs、可变byte、异租户、旧 schema、无原件/非canonical、撤销、错 hash/case/执行ID、未提交origin拒绝。

返回 None 只表示必要持久证据校验结束；根 bootstrap仍只记录不证明签发权，原stored Manifest仍可描述性，不证明全共同准入/父预算/Source最后COMMIT/真实token/费用/实际transport。不得以本入口替代P1、P2、P4，也不能声称fixture签名是真实Model结果。原默认migration不安装origin/function；测试仅新fresh保留隔离库显式安装原existing test-only identity/origin guard。

测试先运行缺 module 的真实 RED（不能用assertFalse假RED）；再构建原native fresh Judge申请整组必要准备，捕获其原canonical Manifest，保留原准备rollback，使用test-owned keys创建仅测试用途signed原字节。实际persisted cert/case在新caller触发原origincapture；同事务未提交须拒绝，COMMIT后独立Issuer caller必要读可过，另 runtime ACL拒绝、输出/原hash/元数据/epoch/revoked/旧purpose和提前错误入口拒绝。签名case用于必要存储合同测试，不构造真实transport或jointreceipt。所有fixture数据留隔离库，不删、不回放。专项及已有相邻持久reader测试原生累计，失败保留；纯crypto285不重复。无UI改动无需浏览器。

收口：原before/after产品和旧evidence hash、nativeDB/cluster/xid状态、专项/相邻输出、方案一致性/风险复审、m1精确文件提交、AOS/Prime/原检查点同步。完整Goal、原atomic/typed/Judge Tasks继续ACTIVE；后继依赖真实joint/transport/rootbootstrap协议，不以必要读者作为业务完成。

原生r1发现：旧 `derive_certificate_identity` 硬限v1，因此v2被原42501拒绝，事务回滚；不改变/放宽该触发器。新module内增加显式隔离安装 statements：独立 `original_target_certificate_identity_binding` 与窄 INSERT 原件派生触发器，只接受v2 Target，保留原根→证书锁、全局 `identity_epoch` 的同 purpose/key/撤销状态机（原transition触发器继续执行），FK到原证书与原全局身份头。无runtime grants、无正式migration、无旧回填。新reader从此v2绑定与原全局identity_epoch读当前撤销头，不建立第二个身份状态机。触发器的header/metadata绑定仍不授root/签名/执行信任，consumer必须重验完整原签名。新原件不可变/FORCE RLS/Owner NOLOGIN边界不变。

相邻旧测试固定2026-10-08至09窗口已过，本轮记录原失败，不改旧日期原件。下一新隔离attempt通过测试专用fixture重新生成当前窗口的真实Ed25519旧v1证书，供原v1 reader回归；它是新测试证书，不是延长旧证书/审批。旧v1产品/测试文件hash保持不变。

r2专项与新鲜v1相邻2PASS/64.17s后，r3扩大到直接原全局identity撤销（本次测试事务rollback，不改已提交原件）、绑定原件immutable/ACL、原binding各hash/epoch/租户负门、原身份行真实锁等待后cert期限重读。r3使用本次新生成的8秒测试证书（严格短于原Judge截止，非延长或回放r2证书），在实际阻塞证据成立后等原cert期限经过再释放锁，核最终interval拒绝；Consumer只读结束为ABORTED。r2精确两文件快照保留，r3新DB/目录/结果不覆盖。
