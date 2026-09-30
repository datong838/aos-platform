# BG00EM 独立消费者服务合同与调用者边界

基线AOS-001001/m1@1f4b8284；复习231-1/3/4/5、BG00EE原子消费、BG00EA原actor Receipt读取、issuer contracts/auth/attempt/service。已有消费者SQL只认识独立DB caller与批准maker/checker，不能把任意同租户OIDC持有者等同于命令原actor。

## 接线决定

首个正式消费服务沿用原actor恢复边界：请求主体必须是原Proposal maker，当前持久owner/admin角色，独立checker批准仍由原SQL重验；不增加转授或替他人执行能力。actor来自重新验证的外部OIDC，禁止请求正文自报actor/roles。当前没有正式外部身份，先完成无副作用合同和DB门验证，保持服务未开放。

命令固定scope、Proposal ID/hash、ApprovalEvent ID、targetContentHash、bindingHash；令牌为SecretStr；不接候选正文、SQL、DSN、连接角色或自选幂等键。消费幂等键固定Proposal ID。Inquiry携同一精确引用但不能提交新动作。传输requestHash覆盖全部引用和scope、排除token与consume/reconcile模式，真实subject另写持久attempt；token刷新不改变同一请求身份。

服务执行序列：外部OIDC/tenant→原maker与当前成员DB门（写时与消费同事务，不能只预检）→持久attempt reserve→最多一次SQL消费→独立只读Receipt对账；任何UNKNOWN/已attempted仅对账，不再消费。原Receipt observed不等于当前active。DB门需后续新增actor-aware窄函数/迁移，不能给caller表SELECT或把凭据回放普通API；在此之前不开放HTTP/IPC消费。

## 精确文件与顺序

1. 新`services/aos-api/aos_api/aip_network_consumer_contracts.py`及`services/aos-api/tests/aip/test_network_consumer_contracts.py`：先RED，严格字段/标识/哈希/Secret序列化与inquiry.matches。纯合同不执行DB或网络。
2. 上述通过后再登记actor-aware SQL、外部认证和attempt/service精确文件扩展Lease，补真实PG正向与错actor/撤销/过期/并发/未知结果证明；不以合同测试冒充服务完成。
3. 专项/累计/复审/verification/D-waves/上下文及精确m1提交。当前真实库118只读，代码121未部署；迁移必须独立一致备份/克隆/零窗口，不启Host/worker/Provider，不读商城源/旧12Run/手工run_definition，不push，230 L0挂起。

## 第4/9步检查点

纯请求合同已实现：schema严格整数1、SecretStr JWT形状、精确标识/哈希、拒绝额外字段，固定幂等键Proposal ID，requestHash绑定scope/ProposalHash/Event/target/binding，token刷新不变。缺模块RED退出2后，与issuer合同相邻累计31 passed / 5.42s / exit0（句柄27932已终态）；没有验证真实JWT或授予执行权。代码尚未提交，Task/Lease BG00EM仍ACTIVE，authority仍AOS-001001。

下一步先扩展计划/Lease：新增actor-aware同事务SQL wrapper，核原maker与当前owner/admin及完整请求引用，再调用现有120消费；只读对账wrapper也核原actor与精确引用。后续外部OIDC复验、持久attempt与服务分派仍未完成。不得把DTO GREEN收缩为整波完成；当前真实库保持只读。

## Actor SQL精确扩展

新增`services/aos-api/alembic/versions/a0v_122_network_consumer_actor.py`与`services/aos-api/tests/aip/test_network_consumer_actor_pg.py`。两个固定8参数函数（scope、Proposal/Event、受信subject、Proposal/target/binding哈希）：写函数同事务锁Proposal及原maker当前membership后调用120；只读STABLE函数同快照校验后调用121。均独立caller/owner与tenant匹配，PUBLIC EXECUTE撤销，仅caller可用。不修改旧函数权限或已有连接消费者；这些仍是可信独立进程内部原语，不能声称已把持有DB凭据的进程变成不可信客户端。人类subject只能由未来服务验JWT后传入，当前不开放请求入口。

现有receipt工具不支持扩展活跃Lease，用同一m1单写者补登记BG00EM-ACTOR子任务覆盖新增两文件，仍属本波，不另行并发写入。

锁序复核：wrapper先锁Proposal，核原maker当前membership；实际新消费沿用120按subject排序锁maker/checker并重验，避免wrapper先单独锁maker造成相反maker/checker请求死锁。只读对账不加锁，按当前语句快照校验成员。旧Receipt回放不产生新写入。RED句柄73972终态exit1、7 failed，122函数尚不存在，连接层按约定脱敏PG错误；完成实现后须真实PG验证，不能把脱敏错误本身当成精确拒绝证据。

## 外部身份精确扩展

新增`services/aos-api/aos_api/aip_network_consumer_auth.py`与`services/aos-api/tests/aip/test_network_consumer_auth.py`，同写者补Lease BG00EM-AUTH。复用issuer现有外部配置检查与auth.resolve_principal，不改全局认证默认值，不复制JWT验签、不伪造issuer决定DTO。消费者仅接精确Command/Inquiry类型，每次重新验证token，严格OIDC/exact tenant/nonempty printable subject，错误统一脱敏。body的哈希绑定不等于JWT真实性，身份门单元测试不作当前正式身份验收。issuer实现保持不变，累计其原认证测试防回归。

## 持久attempt精确扩展

同写者BG00EM-ATTEMPT Lease：修改`services/aos-api/aos_api/aip_network_issuer_attempt.py`，仅将已存在的receipt持久化后半段提取内部`_reserve_attempt_receipt`函数；issuer调用参数及历史文件名、JSON格式不变。新增`services/aos-api/aos_api/aip_network_consumer_attempt.py`、`services/aos-api/tests/aip/test_network_consumer_attempt.py`。consumer严验Command/Principal和scope，固定Proposal ID幂等键；调用同一O_EXCL、0600、fsync实现并指定独立namespace。禁止用issuer DTO伪造决定或复制第二套持久化状态机。测试真实文件、并发唯一赢家、重启后重复、哈希/subject冲突、残缺Unknown、权限/符号链接以及issuer原回归；不以本地attempt代表业务Receipt。

## 一次性服务组合

新增`services/aos-api/aos_api/aip_network_consumer_service.py`和`services/aos-api/tests/aip/test_network_consumer_service_pg.py`，BG00EM-SERVICE同写者Lease。服务只接受固定ConsumerDatabaseConfig与精确Command/Inquiry，不接受运行时connect factory或自报Principal。每次外部鉴权后先独立readonly actor查询；已有observed/conflict直接返回，unresolved才允许争取持久attempt；写事务再次执行122原actor门并调用120。任一AlreadyRecorded/Unknown只能再次readonly，Conflict直接拒绝；数据库写/commit异常不重试，独立只读对账判断。最终observed仅代表原Receipt，未宣称当前active。

调用122前校验函数owner/SECURITY DEFINER/search_path/volatility/ACL，连接沿用现有精确身份检查。read同时校验121依赖以免依赖ACL漂移；SQL返回结构与精确引用必须相符。

测试分层明确：真实isolated PG+文件验证服务DB组合、独立连接commit后断联模拟与无重复；测试中身份适配替身只隔离已单测的OIDC边界，不能当正式服务或当前外部身份验收。正式OIDC、进程/凭据隔离和部署仍独立门。无HTTP/IPC入口，无当前库写入。后续需要真实OIDC集成证据，不能用本波替身组合证明替代它。
