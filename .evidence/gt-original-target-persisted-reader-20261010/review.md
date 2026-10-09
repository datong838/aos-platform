# v2 持久 Target 必要证据实现与复审

基线 6d43c18cf / AOS-001664。Task唯一同owner，两新增精确产品/测试文件，原untracked reader/authority/migration保持保护且没有夹带；正式库/Provider/Host/worker/浏览器服务不动，UI无变化无需浏览器验收。新reader执行原私有Issuer SERIAL同caller SELECT与retained root→certificate→原全局identity锁，canonical v2整组/证书/结果字节、header、raw wire/output哈希和真实Ed25519校验；仅None必要结果，不授派发/准入/可信bootstrap。

RED：模块缺失真实ModuleNotFoundError。原生r1 2FAIL/64.17s：v2用旧v1 identity派生器被42501拒绝；相邻旧固定窗口到2026-10-09已过期。保留r1原log/绑定hash/result和只读回读（本v2 execution的manifest/cert/case/origin全0；失败签名写事务没有记录xid，不造ABORTED字段）。新增独立v2绑定表/严格Target v2派生器，复用原global identity_epoch/transition/withdrawal，保留原v1trigger/defaultmigration/runtimeACL。新鲜旧v1测试证书只修改隔离runner的测试fixture，不改旧产品/测试或原证书。

r2 2PASS/64.17s；r2精确两文件快照已保留。扩大r3后2PASS/72.23s、8既有warning。r3包含原未提交结果拒绝、真实提交后必要读正向、18负门：actual output、mutable、case/manifest/三hash、identity bool/epoch、root epoch、certificate epoch bool、canary/runtime、绑定原件不可变/runtime ACL、原global身份撤销、实际身份锁等待过期、certificate撤销。撤销探针在独立测试事务rollback，不重写既有身份原件；无新身份状态机。

真实等待：reader xid28548/pid84680被原identity行blocker84679锁住；19:02:05.968809 UTC启动，原本次新证书deadline19:02:13.778732，释放后19:02:13.801788因contained certificate interval拒绝。独立原生回读reader ABORTED、原测试字节producer28534 COMMITTED、whole准备事务ABORTED/两原parent0；manifest/cert/case/origin各1属于test-only signed存储，绝不等于真实Target运输或完整joint准入。Source actual-end不由该COMMITTED状态推断。

独立域检查：首轮新legacy测试key误复用原global identity ID，被原42501 MODEL_IDENTITY_BOUND_OR_REVOKED正确拒绝，证明共享原身份头保护有效；保留失败及READ ONLY回读row0，不改/复活原identity。新独立legacy身份probe中v1旧绑定接受，新v2绑定拒绝v1（42501 ORIGINAL_TARGET_CERTIFICATE_BINDING）；probe全部rollback，独立ABORTED/manifest0。与r1 v2进入旧trigger的拒绝构成双向域边界，无旧schema放宽。

方案/代码复审：DB语句仅受控schema/表常量，所有外部值参数化；角色/作用域/隔离/原samecaller/nativebytes限制先读；origin精确case/hash并要求非当前caller COMMITTED，root/cert/identity锁保持至原caller退出；最后DBclock在所有wait之后重新核所有签名窗口。可变/拷贝模型仍由原严格typed模型重解析；所有psycopg错误fail closed，不repair/retry事务。显式隔离安装不接原正式migration，不grant runtime，不改旧撤销状态机。元数据trigger不证明签名/根权威；consumer必须完整验签。当前Source最终提交门、可信rootbootstrap、真实transport receipt、完整风险/实际token/费用/共同receipt、Judge晚绑定再准入、Usage/结算/业务自然首链仍pending。

发布限制：原reader/authority等既有依赖仍由原typed Task管理并未整包提交，本次仅当前worktree的必要证据实现；不得宣称clean checkout发布闭合或正式接入。没有独立Prime PASS（旧UNKNOWN不重发），本复审为人工与原生证据对账。完整Goal、atomic/typed/Judge与本持久reader Task继续ACTIVE；本波不发完整产品Delivery。下一登记项：原v2 Target证书/结果的窄生产者与真实joint/transport/root provenance合成，再接原Judge输入；不能把当前metadata证据直接变成runtime grant。
