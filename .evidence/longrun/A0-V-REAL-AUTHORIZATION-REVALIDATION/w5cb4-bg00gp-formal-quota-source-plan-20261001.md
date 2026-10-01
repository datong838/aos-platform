# BG00GP 正式 Quota 来源施工方案

基线 AOS-001056 / m1 4d3d5658；七strong CURRENT、validate GREEN。Task W5CB4-BG00GP-20261001。231-5首链/审批/费用、231-3配置五依赖与449接续已复习。只在全迁移临时库演练，不连接/重启/迁移当前真实实例。

## 证据驱动的必要依赖

ContentBudgetCommandOwner._prepare_sources 调原 ModelRuntimeResolver 并 require_exact_active quota，审批前池token覆盖依赖该Quota。现 publish_quota 对所有active抛QuotaPolicyApprovalRequired；固定aip_activate_quota_policy在115预留却无专用producer。旧Model测试通过_model_governance_history_fixture直接写active，不可作为合法来源。Budget/price已有签名费用生产接口，本波先补缺失Quota，再回完整Review→AgentRun→审批→Capacity→GE held联合，不缩小业务目标。

## 最小实现合同

复用GO原ActionStore/Draft/Approval及签名Guard issuer、持久attempt；以固定第三类Quota DTO/Action接入，不开放任意策略/表/函数。Quota来源表仍aip_model_governance_policy_*，不搬表、不新建审批权威。原Store只发布draft；target只准draft修订N→active N+1，其余字段完全相同。source原publish Receipt、head版本、payload/hash/tenant重验；R2独立maker/checker、当前owner/admin、有效期不超过15分钟；缺身份继续禁入。

- aip_guard_policy_activation.py：固定Quota spec和内部常量表映射、对应生命周期/元数据名，保持原Egress/Data行为与hash格式；表名来自代码闭合集，不接受调用者输入。
- aip_guard_policy_issuer.py、aip_action_store.py：严格Quota DTO和固定Action加入既有专用生产/审批门；通用入口保持拒绝。
- aip_quota_policy_consumer.sql：新增版本a0v130固定Quota函数；核原批准/Draft/hash/currentmaker/checker/固定metadata/head/原sourceReceipt、Quota全DTO硬限额与组合条件。串行事务写active/head/原governanceReceipt，结束DB时钟重验；只读历史receipt不授新执行权。
- aip_guard_policy_consumer.py最小提取固定类级函数标识，aip_quota_policy_consumer.py复用签名认证/单次尝试/未知只读对账，固定130函数。请求不携带函数名。
- a0v_130_quota_policy_activation.py：additive正式Quota metadata、原Guard issuer/caller/owner限定扩权至Quota表/函数、active/head/Receipt与审批触发器；原129迁移与SQL不改。Budget同表行不受Quota门误伤。部署到当前实例仍独立恢复波。
- test_quota_policy_activation_pg.py：RED运行角色直接active写与metadata缺失；原draft→真实TLS签名maker/checker→低权consumer正向，错签名/错scope/自批/撤权/源漂移/过期/未知结果/并发/单Receipt；原模型治理reader读取正式产物。先测最小根缺口，逐步补齐完整合同。
- 兼容范围：_model_governance_history_fixture.py与公共签名fixture改Quota为合法生产来源，原Budget历史read证据仍明确不计正式联合；Model/治理Store引用改为返回真实revision；conftest清理保留迁移正式Quota对象。

## 验证与收口

全迁移临时PG；不禁触发器/伪造Approval/hash、不mock正式来源；隔离IdP身份不冒当前用户正式身份。先RED、最小实现、专项及GO182相关累计+Quota/治理Store，复审低权范围、SQL NULL/DTO边界、未知不重发与旧行为；verification记录命令/exit/失败。m1精确提交→Task/Delivery/CAS/Prime/450/D-waves。没有UI变化时browser不适用；后续HTTP/UI与当前实例恢复、自然经营首链/八场景/观察发布仍未完成。

### 兼容来源具体调整

公共formal_guard_sources增加固定Quota类型，按闭合类型选择原Governance Store及固定Quota consumer；有效窗口与初始版本不自动修复。旧_model_governance_history_fixture仅Quota分支改正式链，Budget历史分支保持明确历史read证据。Model ref取返回revision2；治理Store的到期断言改为已合法生产active在effective_until精确边界拒绝，不伪造过去过期active。client清理保留QuotaPolicyRevision。正式身份文件沿GO独立passfile，不混用其他角色。

### 当前 Quota reader 补门

复审发现 require_exact_active 对Quota只读指定修订，不核当前head，旧active引用可能在暂停/换版后继续进入运行依赖校验。追加独立Task W5CB4-BG00GP-READER-20261001，仅改 aip_model_governance_policy_store.py 的Quota准入分支，沿既有development Budget current-head比对方式核revision/hash/active；get_quota按版本历史读取保持。先以真实签名产物→原Store发布suspended/draft后旧引用应拒绝的RED证明，不将普通read声明为完整执行事务锁证明，正式业务执行仍须原事务来源重验。

当前性补门细化：Quota准入读取当前head及其原revision/hash/lifecycle。读写事务使用FOR SHARE OF h，TransactionBoundConnectFactory下锁持有到外层结束，并让过时SERIALIZABLE快照在并发变版时拒绝；显式READ ONLY只读观察，不取写锁、不授运行权。追加双连接锁与过时快照反证；不改Budget分支和历史get。完整运行时限与安装fence仍由原执行事务组合验证。
