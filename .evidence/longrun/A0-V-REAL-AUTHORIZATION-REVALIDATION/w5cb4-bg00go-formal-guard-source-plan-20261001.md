# BG00GO 完整首链来源：正式 Egress/Data 生产链施工方案

基线AOS-001055/m1 eedf02e6，231-5 §2/5/6与231-3当前配置五依赖合同、448接续已复习。两仓m1，七strong CURRENT，validate GREEN。GO为进行中，不把方案或RED当GREEN。

## 来源审计与选路依据

完整路径必须有Review→TaskRun→AgentRun→首生Action→Capacity→GE风险预算held。本次不能复用旧test_ecommerce_content_review_pending_pg：固定a0v111、关闭预算触发器、手填Approval/hash；其上游full_graph直插运行与Skill。configured_pair费用配置本身由真实签名消费产生，但Provider引用占位Egress/Data，不足以通过真实ModelRoute。因此先补正式配置来源，不改reader放行。

publish_provider要求有效Egress/Data；publish_egress/publish_data_classification对所有ACTIVE均无条件ApprovalRequired；ActionStore对两个固定ActionID也拒绝无专用producer；仓库只有Network专用producer/issuer/consumer，且Network必须引用active Egress。不能拿历史active seed绕开这个根依赖。aip10_002给runtime策略表INSERT，需用隔离PG核实直接active写边界。

## 正式合同（沿现有审批、不可变修订、Receipt与低权消费）

1. 只支持固定aip_activate_egress_policy与aip_activate_data_policy，不扩其他Action。沿现有EgressPolicyRevisionCreate/DataClassificationPolicyRevisionCreate与R2 maker/checker；所有网络/数据硬边界沿DTO，未知不得补默认成功。
2. 已有Store发布DRAFT并返回原Receipt；专用producer固定当前Draft精确revision/hash、headVersion、下一active候选完整canonical hash、tenant、ActionType、有效期及binding。每次OIDC验证；当前唯一owner/admin maker；current metadata、membership及独立checker同事务核验。approvalRef文本不是批准权威，实际批准始终来自不可变ActionApprovalEvent与消费Receipt。
3. 原AipActionStore保存Draft/Proposal/Approval，禁止新审批表。新guard入口仅精确类型，通用producer/checker及外部Action executor继续拒绝这两个固定控制Action。签名issuer独立数据库登录身份、SCRAM/passfile/NOLOGIN默认部署门；不从Web/API借角色或凭据。
4. additive a0v129只在全迁移临时PG先验：固定两种ObjectType/ActionType元数据且保留ID；独立guard issuer登录边界；低权consumer_call/consumer_owner；active INSERT与受保护head/Receipt只允许受限消费函数。不改现有Network/Budget权限，不给consumer写审批权限。
5. consumer SQL在同一串行事务核scope/actor/current maker/checker/不可变Draft/Approval/撤销/精确head-CAS/DTO完整边界/有效期，写active revision+head+原guard receipt一次；相同proposal/event/hash只读幂等，篡改拒绝。各策略的版本与Receipt独立，Egress不隐式激活Data或Provider。
6. 先正常SQL角色授权及边界，再启专用producer/issuer/consumer；迁移部署到当前实例须独立恢复波的一致备份、克隆全链与零执行窗口。本GO不连接/迁移真实库、不开Host/Provider、不读取商城源。

## 文件级清单与执行顺序

- 新aos_api/aip_guard_policy_activation.py：两种精确候选、来源/metadata/member/binding/独立checker guard；preview/propose/decide服务；不能直接active写。
- 改aos_api/aip_action_store.py：精确Guard构造器和这两Action的专用内部校验接线，其余路径不变。
- 新aos_api/aip_guard_policy_issuer.py：复用external-only OIDC验证基础、独立DB身份检查、决策与只读未知结果对账；不暴露秘密或借Web运行角色登录。
- 新aos_api/aip_guard_policy_consumer.sql与aip_guard_policy_consumer.py：唯一低权函数、真实JWT调用者与精确单次消费/查询；现有guard Store不放开active直写。
- 新alembic/versions/a0v_129_guard_policy_activation.py：固定metadata/DB角色/触发器/RLS/受限函数与append-only门。对已有ID或角色权限漂移失败关闭，不能overwrite当前数据。
- 新tests/aip/test_guard_policy_activation_pg.py：先RED现有策略表直接active写、固定metadata与合法来源producer缺口，再真实Draft→签名checker→低权consumer→原Provider依赖读取；不直插批准、不禁触发器、不monkeypatch来源校验。
- 新tests/aip/test_guard_policy_activation.py：输入/跨scope/固定Action/无效签名/未知结果不重发。只有配套实现范围确定后再创建，不为凑测试数量提前写占位。

## 验收必须覆盖

### 精确来源绑定接口补充

在 `aip_guard_policy_activation.py` 先实现 `build_guard_activation_target`：输入原 Store 返回的 Draft、同类 active candidate、scope 与预期 head version；只允许 lifecycle=draft→active、revision+1，其他业务字段必须逐项相同。源 payload 的 tenant/hash 重新核验；Pydantic model_copy/model_construct 绕过校验也不得穿透。绑定固定 Action、策略种类、原 Draft hash、目标 hash、租户及 head revision/version。`read_guard_activation_source` 在调用者事务中锁 head，读取精确原修订及原 publish Receipt，重新核验列/payload/hash/actor/时间与 Receipt，且确认当前 runtime/GUC scope。该函数本身不提交、不写批准、不激活。先隔离 PG 验当前 head 漂移、跨 scope 和非 Draft 拒绝；后续 maker/checker 与 consumer 必须使用相同来源合同，不能拿纯绑定测试替代批准消费链。

### 独立 checker / 签名入口补充

`GuardPolicyApprovalGuard` 在原 ActionStore.decide 的事务内重验独立当前 checker、当前 maker、原不可变 Draft/proposal hash、固定 metadata、精确来源与时限。已决 Proposal 只用于原 key 只读对账，不新增第二个决定。私有 `decide_guard_activation` 不提供默认 DB factory，并要求 issuer session_user / runtime current_user；外层事务包住原 Store，commit 前再以数据库 clock_timestamp 核过期，防锁等待期间跨过时限。

`aip_guard_policy_issuer.py` 提供 `GuardMakerCommand`、`GuardDecisionCommand`、签名 maker 与 `GuardPolicyIssuer.execute/inquire`。每次命令重新解析严格 DTO，external-only HTTPS OIDC/JWKS 校验实际 JWT；签名 Principal 只由认证模块产生。issuer 必须精确 expected_database、独立登录 aos_guard_approval_issuer、低权无额外 role、写 SERIALIZABLE / 查询 REPEATABLE READ READ ONLY。调用前只读式预检当前 checker；复用现有 `_reserve_attempt_receipt` 的 fsync/O_EXCL 私有目录持久标记，namespace=guard-policy-issuer/v1，不存 token。一次决定调用后只读精确 ApprovalEvent 对账；遇已尝试/commit未知只 inquiry，不能重新决定。原批准表仍唯一 authority，不新建批准或决策表；标记只是防重发。正式部署还须单实例持久目录与独立身份配置，不借 Web credential。

隔离验证使用既有 https_signer（真实 TLS、RSA JWT/JWKS，仅 DNS 指向临时本地服务器）与临时 SCRAM LOGIN/passfile，结束恢复 NOLOGIN/PASSWORD NULL。正向来源由原 Store + signed maker + signed independent checker 产生，不手填 Approval/hash；错误签名、跨 scope、自批、成员撤销、来源漂移、commit未知后的只读重复、普通 runtime 假充 issuer 均须验证。此证据不是当前真实组织的外部 IdP 授权。

### 低权消费接口补充

`aip_guard_policy_consumer.sql` 安装 `aip_guard_activation_a0v_129(org,project,proposal,event,actor,proposalHash,targetHash,bindingHash,write)`，security definer 的 owner 仅为独立 NOLOGIN consumer_owner；caller 无表权限/role membership，只有此函数 EXECUTE。write=false 在只读事务完整预检或核对既有 Receipt；write=true 在 SERIALIZABLE 事务锁原 Proposal/Draft/Approval/member/metadata/head，重复核验后只追加目标策略修订、更新对应 head、写一条激活 Receipt。函数内部校验角色/GUC、当前 maker=签名 actor、独立 checker 与资格 hash、原完整 Draft/hash、withdrawal/expiry、固定 metadata、原 Store source Receipt、精确 source/candidate/hash/binding、两类 DTO 的硬边界；提交前 clock_timestamp 再验。已存在 Receipt 是历史对账，仍验证 actor/成员与原产物精确匹配，不能当新授权。

Python consumer 每次 JWT 认证，核精确 database/caller、函数 owner/definer/调用权限与只读/串行隔离；无默认连接/credential fallback。只读预检通过后，以 proposal 为唯一幂等身份复用私有持久 marker（namespace=guard-policy-consumer/v1），至多调用一次写函数，随后只读 Receipt 对账。caller 输入 hash 不成为 authority；必须与数据库原事实独立一致。当前真实库不部署。新增 SQL 沿 a0v128 的版本迁移加载配套 SQL 文件方式，在 m1 同一提交固定代码与迁移。

### 旧 Guard 来源夹具改接正式链

累计已证明旧 helper 直接 active INSERT 失效。追加独立测试 Task scope，生产门不变。将 `_runtime_guard_history_fixture.py` 改为真实隔离签名生产辅助：原 Store draft1→signed maker Proposal→独立 signed checker→低权 consumer active2；保留旧函数名供旧测试调用，但返回修订必须按正式产物读取，不冒充历史 revision1。输入的业务字段/有效期保持原样，过期/非 active/非初始候选明确拒绝，不能把坏输入自动修成合法。

为避免 HTTPS fixture→Network atomic tests→precheck tests→新 Guard fixture 的循环导入，把既有 https_signer 及本波 issuer/consumer 临时 LOGIN fixture 移到上述中性辅助模块；原 signed HTTPS 测试及本波测试仅改 fixture import，不改变签名/角色/约束逻辑。六个旧使用模块显式导入 autouse `formal_guard_sources` 及其 fixture 依赖，正式连接生命周期仍由 pytest 管理，不手工调用 fixture、不关闭触发器。

复查发现另有10个 Network 测试模块通过 `_approved` 间接使用来源函数；只在6个直接调用模块导入 fixture 会遗漏它们。因此将 fixture 改为惰性：在 `tests/conftest.py` 注册公共 fixture，autouse 仅设置测试级 ContextVar 回调；实际调用 Guard 来源函数时才经 request.getfixturevalue 获取 TLS/issuer/consumer/临时目录，未使用该来源的测试不启动 TLS、不改认证环境、不启角色 LOGIN。六模块无需重复导入所有 fixture，仅原 helper import 保留。追加 conftest 独立 Task scope；不改变现有数据库隔离/迁移/清理逻辑。

改接后 Model Runtime 兼容测试暴露第二个既有直接 active Network 种子，现有 a0v120 已会拒绝。对已登记 Model Runtime 测试内的 publish_network_policy 也改走现有 Network producer→独立 signed issuer→低权 consumer，私有登录/passfile 在隔离 fixture 中单独创建和恢复；生产 Network 模块不改，既有历史 Network reader 测试仍不计正式来源。TLS 失败用例以准备完成后的 JWKS 请求数为基线，验证失败请求不新增网络访问，不再要求准备阶段也为零。

文件：`tests/aip/_runtime_guard_history_fixture.py`、`test_network_consumer_signed_https_pg.py`、`test_aip_runtime_guard_policy_store.py`、`test_aip_network_policy_store.py`、`test_aip7_model_runtime_store.py`、`test_network_approval_precheck_expiry_pg.py`、两个历史显式 clone 的 `test_aip_network_policy_action_producer_pg.py`/`test_aip_network_policy_approval_consumer_pg.py`（旧 clone 环境仍不作为当前验收）。本波 `test_guard_policy_activation_pg.py` 已登记，移出重复 fixture。Guard store 旧固定2026-08过期窗口改为本次当前时间；精确 ref 取实际 revision2，增加旧 draft1与过期时点拒绝断言，保留租户隔离。Model runtime ref helper增加可选revision，仅Guard来源传实际版本，其它原引用仍默认1。历史Network自身的人工种子测试边界照原披露，不计入本波正式来源正向。

- 原Store的draft/blocked/suspended历史逻辑保持；未经批准active直写、role切换、元数据篡改全拒绝。
- 两策略独立正向：实际签名maker/checker→原Draft/Approval→低权consumer，原require_provider_dependencies读取成功；provider不发请求。
- 自批/跨租户/成员撤销/候选或head漂移/expired/withdrawn/错误kind、接口旁路、并发/失败rollback/同key不同hash、未知结果只读对账。
- 一次Receipt、无新Approval重放、dev-org零副作用；真实全部迁移库，不能用简化schema、当前库、历史clone模板或纯模拟代替。
- 累计原Action/Network/Budget/Guard回归；若现有历史read夹具需要调整，只作历史专用隔离证据并明确不计入正向合法链，禁止通过放宽生产门兼容fixture。

## 后续原目标不缩小

正式Egress/Data齐备后，继续Network/Quota/Budget/Provider/Model Eval/RuntimeRoute的合法生产接口联合，再接真实Review来源与Content Owners到GE held；HTTP/原Action可读预览/browser及当前实例独立恢复、自然经营首链、八场景、连续观察发布仍须实际证明。Goal active。不能把本根依赖的代码通过称完整首链通过。

### 消费中审批过期的事务回滚验证

在已登记的 test_guard_policy_activation_pg.py 增加两种策略参数化用例：独立签名 checker 正常批准短有效期；仅在隔离库对该 proposal 的真实 Receipt INSERT 增加延迟，不停用任何安全触发器。临时 sequence 证明实际到达写入；消费结束后必须 unresolved、active 修订为零、head 仍为 draft1/version1、激活 Receipt 为零，原批准仍存在。finally 清理故障注入对象；当前实例不操作。

### 累计暴露的 client fixture 清理边界

16组累计中 client fixture 删除除四种演示类型之外的全部 meta_object_type，导致 a0v129 正式 Guard 类型消失，后续46例均 GUARD_OBJECT_METADATA_DRIFTED。仅在已登记 tests/conftest.py 的清理 SQL 保留 EgressPolicyRevision、DataClassificationPolicyRevision 两种本波迁移固定对象；不补造元数据、不修改生产 reader。用包含 client 调用且后续读取正式来源的原16组顺序验证回归，防止只跑单文件掩盖顺序污染。

第二轮相同累计暴露同一清理 SQL 也删除 NetworkPolicyRevision（a0v117 正式对象），41例 FORMAL_NETWORK_OBJECT_TYPE_UNAVAILABLE；将该既有正式对象一并保留。此为实际累计证据要求的第三个固定对象，不扩大到任意保留用户测试对象。

### 共享 passfile 的正式身份隔离修复

第三轮181通过、1失败，单独复现仍失败。源码核验显示 Network live_test_config 先写 private_passfile，而惰性 guard_issuer_factory 随后把同一路径覆写成 Guard issuer 凭据，导致后台 Network 连接在到达 Receipt 前失败。修改已登记中性 helper：guard issuer 使用同目录独立 guard-issuer-pgpass，0600，并在 finally 只清理自己的文件，不覆盖 Network private_passfile。保持原失败用例不改，用原 Network 到期回滚用例与 Guard 专项验证角色共存。
