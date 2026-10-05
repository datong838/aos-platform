# 容量 Source 依据撤回与审批提交协调

基线 m1 523b83bc / AOS-001350；独立 Task gt-provider-capacity-evidence-epoch-20261005。完整容量Source与b90 Task继续ACTIVE。本波修补已完成Source候选审查的事务当前性，是正式issuer后继必需依赖，不建立供应商或正式账户权威。

## 已读源码与问题

Source guard在同conn重验account/basis/旧request的EvidenceBundle元数据，但get_evidence_bundle只是普通SELECT。原revoke_evidence_bundle通过原receipt/append-only revoke_event插入，旧license头锁只保护已存在LicenseSource，不保护容量Source引用所有Evidence。本波先用实际审批读取之后暂停、原撤回提交的并发证明缺口；不把两个先后顺序的独立调用冒充竞争。

## 文件级实现

- services/aos-api/alembic/versions/a0v_149_capacity_evidence_epoch.py：独立NOLOGIN/no-membership/no-extra-flags epoch owner；private epoch表按tenant/bundleID，FORCE RLS，无runtime/PUBLIC表权限；schema-qualified固定search_path的SECURITY DEFINER reader和revoke BEFORE/AFTER trigger。reader取得FOR SHARE；writer BEFORE初始化并FOR UPDATE，AFTER递增epoch，锁持有至caller事务结束。旧许可证角色和函数不扩权，原撤回Store不改。
- services/aos-api/aos_api/aip_provider_capacity_evidence_fence.py：原native conn/positive TenantScope/严格Evidence exact输入、owner/ACL/函数边界审计；去重稳定排序锁全部bundleIDs，再在同conn重读原严格frozen/非撤回/hash元数据。runtime只拥有reader EXECUTE，任何owner flags/membership或表/函数ACL漂移拒绝。
- services/aos-api/aos_api/aip_provider_capacity_source_action.py：account/basis解析及原request取得之后，将旧request/account/basis全部Evidence传入fence，在原写入前完成锁及重验。不能漏掉与新basis不同的原request依据；原角色/Provider/proposal锁继续使用原合同。
- services/aos-api/tests/aip/test_provider_capacity_evidence_epoch_pg.py：actual Source review读取后与原撤回竞争RED；read-first writer真实数据库锁等待、审批先提交随后撤回；write-first/post-snapshot情况下reader拒绝或原SERIAL冲突；SQL原撤回insert触发、ACL/角色漂移和canary拒绝。
- 本目录：方案、终结logs、验证记录。

## 原锁与兼容性

原revoke先取得旧license头锁，然后原SQL INSERT上的license triggers及新增epoch writer；容量reader只取得新neutral epoch，不取得旧license头锁。多个Evidence reader按bundleID稳定排序；撤回单bundle写者不反向取得Source proposal或Provider头锁。初始化unique冲突/SSI冲突必须失败回滚，禁止重开snapshot后假称原子。epoch只表示变化顺序，不作Evidence或正式签发事实。

trigger覆盖直接SQL原revoke_event插入，不依赖调用者使用新helper。writer保持原通用tenant/GUC边界，不能因新Source仅positive而破坏其它tenant的正常Evidence撤回；Source reader仍只准org-org/dev-project。原immutability及replay不改，撤回不释放任何预算或容量。

## 验证和交付

督导补充：验证同时初始化、ON CONFLICT重放、原撤回replay和rollback；只有实际插入撤回推进epoch。后继若同时持旧License和新neutral epoch，必须License→neutral epoch，不得反向。另以非正向tenant的原正常撤回/直接INSERT验证writer兼容，Source reader canary仍拒绝。helper除ACL/Owner外还核函数prosrc哈希、固定search_path、trigger注册及enabled状态，不能在DDL漂移后继续声称锁有效。

代码复审再补：真实autocommit连接即使role/GUC正确也会在语句后释放锁，必须先实际RED，再拒绝autocommit、非已开启caller事务、read-only和非read committed/serializable隔离；helper不得自行开或重开事务。RLS精确核唯一capacity_evidence_epoch_scope、Owner角色、ALL命令、permissive及原tenant USING/WITH CHECK表达式，extra或altered policy均拒绝。先真实policy drift反例，再最小审计实现。

实际线程、实际caller事务、实际原Source proposal/ApprovalEvent及原revoke Store，限时事件协调/异常回收；等待需读取disposable PG进程锁证据，不能只用sleep推断锁。new epoch metadata 不作Source发行，read-first审批在撤回之前提交可接受，撤回后后继消费必须拒绝。writer先提交则审批不能成功。针对性与Source/原Evidence/License相邻串行；compile/diff与督导只读方案代码复审。无页面变更，不需要浏览器。

仅disposablePG5433，当前142库无访问/迁移/重启；无Host/worker/现实Provider/Secret/商城源/旧Run/manual/230L0/未知重发/外部效果。正式物理账户归一/供应商依据适用性和时效/private issuer签名/消费器/共享账本/自然首链不因epoch波GREEN而完成；m1单写/no push。
