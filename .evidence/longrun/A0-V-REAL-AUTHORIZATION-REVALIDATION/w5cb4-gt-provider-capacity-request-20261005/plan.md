# GT Provider物理额度配置来源：不可执行精确申请

基线58a7e051/AOS-001346。复习GT-b4共享物理方案及原Provider/Source/Owner reader。完整目标仍为独立批准→共享账户/occupation→旧占用正式切换→同事务预算容量与一次Intent→真实执行证据。此阶段直接建立缺失的配置申请生产记录，不授物理额度或执行，不能把申请提交称完整GT-b4b完成。

文件：新aip_provider_capacity_authorization.py、aip_provider_capacity_request_store.py、a0v_145_provider_capacity_request.py、tests/aip/test_provider_capacity_request_pg.py。Task gt-provider-capacity-request-20261005。严格schema冻结正向tenant、精确Provider、稳定physicalAccountId、Owner请求的并发/token限额、单位、basisEvidenceRef、有效窗口与短申请期限。basisKind固定owner_requested_allocation；请求数值不是已核供应商物理上限，原Evidence元数据引用也不是供应商上限证明。客户端不得自报maker/approval/active/available，数量/修订严格整数，期限aware；所有terms与server maker绑定hash。

Store使用原SERIAL事务，检查aos_runtime和scope、原OIDC Principal同tenant、DB当前Owner共享锁，原Provider current canonical payload及head共享锁，原ProductionContractStore同conn读exact frozen且未撤回EvidenceBundle，仅元数据；不读取业务payload/Secret。DBnow核有效窗口与申请期限。仅写不可变request，authorization固定REQUEST_ONLY_NO_CAPACITY_NO_START、basisVerified=false、executionAllowed=false。原SQL canonical/hash是唯一记录hash来源；同key/body+maker重放，任何actor/terms漂移拒绝，不续期。

新表FORCE RLS，原runtime仅SELECT/INSERT，无UPDATE/DELETE/TRUNCATE，原append-only触发器；CHECK明确非执行身份和body/tenant/maker/hash/期限绑定，未知或缺字段不能借NULL通过。不注册可执行Action/不修改Runtime配置/额度/预留/普通reserve。无当前库迁移。

先契约+PG正向缺模块RED，再最小实现。PGProvider来源走现有真实签名Guard/Provider producer；Evidence经原build fixture，证明原元数据生产而非供应商容量/自然经营来源。实际JWT经本地HTTPS校验；新申请不是正式消费角色LOGIN/发行证书。实测wrongOwner/actor/hash/Provider head/source revoke/期限/canary，replay与immutable/ACL/RLS；原容量/Model申请预算相邻。已有物理缺口xfail保留。

下一须原Action独立checker绑定本完整申请+source/Provider/当前Owner与basis适用性，再固定NOLOGIN发行/消费和共享账户/occupation/切换。申请不是这份批准，不造常数和假PASSED；current142、Host/worker/现实Provider/Source业务内容/外部效果不触碰。

## 独立复审补充：原runtime直接INSERT同样约束

督导发现DB JSON检查未覆盖全部严格申请字段，scope RLS也可能允许canary直接新写；先实际raw SQL RED，再在a145本表新增完整envelope/application/tenant/exact refs的字段白名单、必填类型/数量范围/canonical ID/aware期限窗口及唯一正向tenant CHECK。无新增审批权。独立checker后继仍须完整reparse/hash及原Owner/Provider/Source当前事实重验，physicalAccountId仍客户端申请且不是共享账户权威。

复审二：SQL默认btrim只处理空格，Python strip还处理控制/Unicode空白；先tab账户/newline引用/全角空格账户三例真实raw SQL RED，随后a145在ID/key/maker/physicalAccount/ref ID统一使用与Python strip同集合的显式trim字符，保持请求协议。
