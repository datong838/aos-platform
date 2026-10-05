# 完整容量 Source 正式发行接续方案（方案门，未实现）

基线 m1 ac975e0b / AOS-001351；承接ACTIVE gt-provider-capacity-source-20261005。产品目标仍是共同稳定物理账户及经营自然首链，本方案不替代完整发行/消费者或共享账本。

## 复习所得的实际接口冲突

1. 原 ProviderInstanceRevision 无供应商稳定账户归属。candidate的supplierId/fingerprint只是claim；原获批Source proposal也不证明供应商事实。原LicenseSource只供原许可purpose，不能拿其签发角色/签名政策授权容量。原Registry issuer模式可参考原caller/私有目标库/身份/ACL核验，但不能以配置对象或构造Principal替代真实外部OIDC。
2. 新epoch reader只接受真实aos_runtime、仅grant给runtime且审计该唯一ACL。未来专用private capacity issuer不能SET ROLE runtime绕过身份，不能直接调用现helper并宣称提交协调。需要先登记epoch issuer-read边界的精确后继Task/Lease及方案：保持既有runtime审批路径，新增明确独立consumer/issuer角色所需窄权限与真实身份检查，审计角色/函数ACL白名单；不可在本fullSource Task scope中隐性改a149/SourceAction。
3. 既有a147只candidate表，当前候选引用类型不可被正式consumer接受。正式物理账户、来源Revision与签名provenance必须新additive表/角色/DDL；现fullSource Task scope仅a147，下一DDL/consumer文件应另登记Task，禁止把正式schema塞回已交付候选migration或把candidate直接发布。

## 完整发行须证明的事实及退出条件

- 供应商来源具有独立可信签发者/来源policy exact引用；绑定supplier、稳定账户fingerprint、Provider exact集合、计量mode/窗口、observedAt/validity与原Evidence hash。读取原Source资料的适用性与时效政策，不用统一默认TTL补未知事实；future observation/错误窗口/过期或原撤回拒绝。没有真实供应商来源则真实发行不启用，协议可用明确test-only签名夹具验证。
- Owner分配与supplier已核上界区分，数字只同维度比较；Source独立批准exact proposal/event为授权条款，不能填basisVerified=true自证。固定窗口速率不可替代inflight token占额。
- 正式映射按supplier/fingerprint全域唯一，稳定物理ID不含Provider版本/Secret；Provider不可同时分属两账户。跨tenant真实同账号无法全域共账时拒绝第二分配，不能租户各自拿完整供应商上界。双向唯一、竞争、轮换/同账户多Provider/旧映射不漂移需真实PG反例。
- authenticated外部issuer-origin + 当前maker/checkerOwner + exact批准/Provider heads + 全部Evidence epoch，原SERIAL caller及真实COMMIT内原子发布非执行signed Revision。命令hash签发来源、目标DB角色/ACL、固定search_path与私有配置都验证，未知attempt仅原对账，不换key重发。
- consumer仅接受正式Revision，重验签名/固定发布issuer/批准/current heads/Source失效撤回/epoch；candidate、客户端DTO、runtime伪造行以及fixture外注入签名均拒绝。非执行Revision不自动占额或激活真实Provider。
- 共享occupation/旧活跃占用零执行切换/一次Intent后续继续；完整锁图需对账原Capacity→Budget与旧GTb4顺序，不得沿旧tenant+Provider账户模型拆额。

## 下一文件任务准备

现scope内先完善严格发行command、正式signedAccount/Source契约及私有connection输入合同RED，保持candidate契约兼容；新增正式DDL、源policy reader、consumer及epoch私有角色适配须先补独立精确Task/Lease，职责/锁序/实际两方向竞争方案复审通过再编码。优先解决可信来源与全域映射的原子发布，不能只增加一个便捷输出DTO当发行完成。

当前真实库无读取/迁移/重启；Host/worker/真实Provider/Secret/商城源/旧12Run/manualrun_definition/230L0/未知重发/外部效果仍禁。全程m1单写/no push。
