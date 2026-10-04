# 正式License来源与head初始化合同 v1（设计，不是运行许可）

## 本次源码事实

- production-contracts router315–342：create/build/revoke依赖require_principal，_scope155–156取principal租户；未见这些handler单独调用License发行角色门。require_principal272起执行认证、workspace与scope绑定。这不等于“匿名可写”，也不据静态handler审计宣称整个HTTP权限漏洞。
- DTO CreateEvidenceBundleRequest1307起允许license_summary dict；Store build3179–3266验证exact frozen Brief/计算coverage，把license_summary纳入canonical payload/hash，写frozen修订与build/create Receipt。不是只凭客户端覆盖coverage；但没有在此写路看到独立正式License发行/安装Owner证明。
- readiness license_evidence_available93–119接受EvidenceBundleRevision，检查frozen、license_summary非空、未撤销。属于现preview来源读取，非正式发行合同；b69–b77受限候选也不能由非空字典升级真实源。
- w2_005普通runtime具有撤销事件SELECT/INSERT，FORCE RLS；b77隔离DB trigger+pre-replay锁已解决事务组合，但正式schema没有该head/trigger。
- aip_memory_production_factory.resolve_license_authority88起读取aip_memory_source_revision的license_id/usage_policy/hash，属于KnowledgeSourceRef。不能把另一个资源authority直接套为EvidenceBundleRevision可信初始化；也不能泛称系统没有License resolver。
- signed_session只证制品准入到journal资源，不是business admission；BI有独立ScopedBIIssuerConnection和身份/库/超时/role审计，router默认BI正式发行service503 fail-closed。只能借鉴边界，不能借用BI身份或私有认证创建License权。

源文件完整SHA256保留source-hashes.json。本次仅静态源码路径审计，不曾读取私有passfile/credentials，不运行业务HTTP写路。

## 设计边界与兼容

保留普通EvidenceBundle create/build/revoke接口与Receipt内容及已有正常用途。不能通过禁止所有非空license_summary破坏通用Evidence聚合，也不能自动将旧frozen修订升级正式License。

正式restricted binding/evaluator必须另查可信License发行记录与head。普通preview结果不作为production准入；新的正式读取器必须missing issuance/head fail-closed。现generic readiness preview的兼容与正式reader分离，不能让旧调用者受隐式全局启用影响。

提出两个新表（名称为设计候选，不是现有实现）：
- aip_license_source_issuance：tenant/exact bundle revision/hash、exact installation id/etag、current Owner授权ref/hash、验证过的signed发行身份与政策ref、issuance key/hash/Receipt、issued_at。append-only，同key不同payload冲突；不接受客户端自报issuer/epoch为权威。
- aip_license_source_head：tenant/exact bundle revision/hash PK，issuance FK，epoch>=0。只可信初始化发行事务能INSERT；runtime无INSERT/UPDATE/DELETE；读与受限锁函数最小grant，FORCE RLS。

初始化同事务验证：真实独立发行身份/数据库名、exact当前signed安装/Owner/policy、冻结Evidence源canonical hash和许可证含义（不是任意非空dict）；同事务issuance/Receipt/head epoch0，无正式身份或任一不匹配即拒绝。不能用admin fixture、普通GUC或已有bundle.create Receipt充当issuance。安装epoch/Owner漂移的实际引用来源表/函数尚须b79源码映射后冻结，不能在生产代码猜一个Owner字符串。

撤销：Store _replay之前受限exact head锁；数据库event trigger唯一推进epoch（新key但已有event不推进）。缺head按明确formal source域fail-closed，不对所有通用EvidenceBundle隐式要求新head，以保护普通证据正常撤销；正式source域的判别必须数据库可信issuance关联，不能客户端prefix。rawSQL正式源事件同样受约束，非正式源不能借generic事件变成正式源。原hash/Receipt/历史不改。

Evaluator统一锁序Installation→Registry→按exact稳定排序的依赖heads→Binding/Receipt；SERIALIZABLE旧快照变head40001，无更新和Receipt；已撤销42501。b77证据用于算法，不宣称正式身份或所有revision/八来源完成。

## 精确生产候选文件清单（尚未授权执行真实迁移）

1. 新 services/aos-api/aos_api/aip_license_source_authority.py：可信初始化/读取/受限锁与身份合同；先完成安装/Owner真实来源映射，测试连接不得自动变正式。
2. 新 services/aos-api/alembic/versions/<next_revision>_license_source_authority.py：具体revision/down_revision必须读取当前唯一Alembic head后确定；表/RLS/角色/函数/trigger，与通用Evidence domain兼容；不能预填a0v135当代码最新head。
3. services/aos-api/aos_api/aip_production_contract_store.py：只正式source revoke的pre-replay锁；通用路径保持原行为；不能从body字段声明formal source。
4. 原restricted evaluator实现实际承载路径：b79从signed制品与调用端定位正式文件，不把测试helper搬入生产，也不新增平行runtime authority。新的reader加入issuance/head exact校验，preview不会自动视为正式。
5. 新 services/aos-api/tests/aip/test_aip_license_source_authority.py 与原full-schema PG：ordinary principal/rawSQL不能发权、合法独立issuer、同事务初始化/幂等/冲突/缺源/canary、两race/失效/恢复、新旧domain兼容、migration head/RLS/备份恢复。

## b79 下一已登记施工入口

先只读定位当前唯一Alembic head、signed restricted evaluator真实落点、installation/Owner/policy权威ref、正式issuer身份路径与普通Evidence兼容域；形成source mapping/未决项闭合，不碰凭证。随后一次性全schemaRED证明普通bundle+非空license_summary不能初始化可信head，合法新发行应唯一同事务产生issuance/head/Receipt。签名发行权限、未知Owner等外部条件仍fail-closed；继续独立W-L20与其他依赖合同，不因局部缺身份停止整体Goal。生产代码实现前完善整体文件计划与风险复核，真库迁移独立门不变。
