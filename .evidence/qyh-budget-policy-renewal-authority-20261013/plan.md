# BudgetPolicy续期Authority A波执行计划
Rules：用户AGENTS/工程交付/231完整Goal/唯一writer；Authority2025。上位完整方案 ../qyh-budget-renewal-actor-consumer-plan-20261013/implementation-plan.md 和独立r2PASS消费约束全部继承；A交付不冒充B/C真实部署/原真人批准/价格授权/自然首链。
精确8新文件见registration.json（contracts/identity/store/authority.sql/a0v_162+contracts/identity/PG tests），无现有文件覆盖或旧Lease重叠。先再审原actualOwner schemas/roles/RLS/canonicalhash/外部及原批准本机auth边界，建RED对应未实现的原金融字段/机器真session/唯一checker/currenthead/CAS/atomicReceipt/撤销/并发/unknown/权限负例，然后最小闭合A代码。只允许独立隔离PG中schemasetup/fixture真实调用，没有原卷迁移/角色开启/数据写入；默认新rolesNOLOGIN、无运行路由注册。不得改original ACTIVE拒绝guard、genericauth或userdirty任何文件；发现新不可替代文件先另Scope/方案评审。
原已有Proposal/Preflight复用typed/hash/Owner facts，不把旧inquire的人类Member gate松给机器；MachineRole实认证+boundIssuer边界不能claim凭据compromise immunity；真实CheckerBinding与Deployment闭门。真实PG测试正例为隔离正常低权roles，不是原真人验收。隔离admin仅setup；全套CAS/atomic rollback/lostackreadonlyreconcile/newheadhistory/列授权/RLS/Profile漂移反例及原genericACTIVE合同一致。Code/live独立Prime/Receipt/Authority后立即B精确计划，完整GoalACTIVE。

2026-10-14 合同补齐：上位方案明确要求真人撤销，新增 RenewalRevocationCommand，仅接受原 proposalId/hash、decisionId/hash、显式 reasonCode（approval_withdrawn/scope_changed/dependency_changed）；使用独立 revoke/v1 hash domain，不能借 consume/decide 请求跨操作重用。仍无 actor/批准字段，解析不授撤销权限；实际撤销必须独立 issuer 核原真人 JWT/当前权限/原决定，取得同一 proposal 锁并写 immutable 后继事件。先专项 RED、最小合同实现、专项与原 Proposal/Preflight 相邻回归，完整 A native/codePrime 仍待交付。

2026-10-14 Store/SQL 实施补充：Store 只接受真实 psycopg.Connection，不走共享 DSN/connect_factory fallback；每次调用前必须 IDLE、非 autocommit，由单独 transaction 管理 READ COMMITTED/LOCAL tenant/超时与 read_only。类型、canonical hash、真实角色/唯一真人 JWT 在该事务内复核，调用固定 qualified SQL 函数，无任意 SQL/actor 参数公共入口。结果仅在事务成功结束后返回；提交/连接失败标记 unknown，不能重试，只用原请求独立 READ ONLY reconcile；数据库明确拒绝且已正常 rollback 为 blocked。数据库函数 body/owner/signature/search_path/EXECUTE grants 与 RLS/column ACL 每次调用检查；迁移可通过受控 COMMENT seals 存原生 pg_get_functiondef/policy 表达式哈希，schema migrator 为明确 TCB，不声称能抵御管理者同步改 body+seal。固定白名单和本地源码验证在 B 的真实启动部署中另核，当前 caller 全 NOLOGIN。

原普通 READ ONLY 身份已 metadata-only 核七张原表均 ENABLE/FORCE RLS（original-current-rls-readonly-r1.json）。新迁移要求该基线成立，绝不替缺失原隔离 silently 开启/改旧 policies。新 seal manifest 放在新增 proposal 表 COMMENT，包含原函数/相关表 ACL、列权限、RLS policy shape，保留原表/函数已有 COMMENT；caller 不拥有表或 DDL权限。身份层原直接 SELECT meta_membership 与“caller仅EXECUTE”冲突，改为无 subject 参数的独立 checker_member SQL helper，固定唯一真人和 tenant，只有 issuer_call 可 EXECUTE；此 helper 仅观测 current member，最终决定仍按同序加锁复核。SQL profile 和 Store 独立 catalog/hash检查均需实施，不把自己已被改的入口函数声称为能检测自身被恶意替换的可信边界；schema-admin TCB之外的 drift 必须 fail-closed。

## 八大工作台视觉比对要求（2026-10-14 用户补充）

剩余native竞争/unknown证据：独立fixture source policy id，不改原客户数据；只在schema-admin setup事务里建立测试原表状态，正常角色调用前恢复原guard并检查enabled。用pg_stat_activity真实advisory/row lock等待状态同步两个连接，不以sleep猜先后；验证revoke先提交则consume拒绝、consume先提交则revoke记录不抹历史、同source两proposal仅一CAS成功。commit回执丢失使用libpq发送COMMIT并flush但不读取ack，独立只读看到结果后丢弃连接，原请求仅新READONLY reconcile，不重发consume；证明返回history非未来许可。所有caller临时LOGIN仅fixture，结束恢复NOLOGIN，整波全8文件/full旧cost/generic回归与最终Prime仍要完成，不以这些测试替运营授权。

用户追加八台视觉比对：本波 evidence/visual-20261014 只读记录原 foundry/html 八稿与当前冻结运行 Web 的新鲜并排截图，1280×720、1440×900、1920×1080，保留原页面真实阻断/部分数据态；仅导航已登记八菜单，不点击运行、批准、刷新或来源探测。引用实际 Web 版本，不把候选 HEAD 当已加载代码。同一页面尺寸、明亮主题、展开导航；原稿演示内容与真实状态不等价，业务工作区只能评结构，不能评演示数字一致。恢复原浏览器尺寸与经营参谋入口；差异和待验收项登记 D-wave。此记录不交付完整 A、不改变 Authority/DB/权限，不重验旧读取成功结论；未来相关前端施工须修订对应页面方案、登记 Lease 后修改并同样复查。

r17 fixture诊断：已确认容器DB时钟较host快约1.67sec；短窗口应直接取DB clock_timestamp并只读轮询DB达到同一until再COMMIT，保留2秒原测试期限及原拒绝逻辑，不延长产品门。clone source fixture setup恢复trigger前先SET CONSTRAINTS ALL IMMEDIATE完成待检查FK，仍在单一schema-admin setup事务中，不让正常caller在guard disabled状态调用。r17失败日志/诊断和已提交原测试效果保留只读对账，不在旧数据库重复整套测试；修复仅test_budget_policy_renewal_pg.py后启新r18。

r19追加同source两approved提案native transactionid锁竞争、一成功一23514；fixture-only原canonical INSERT/UPDATE故障令函数返回未提交observed但仅Receipt半状态，真实deferred COMMIT拒绝、无行/无head变化。原guard仍执行、不增caller DML。DB clock观察上限10秒只限制测试观察，原窗口2秒不变；wall-clock修正不以host sleep猜期限。完整旧cost/generic相邻回归下一r20：在本Task evidence/legacy-compat-r20冻结m1 committed services/aos-api（排除userdirty），仅覆盖本Task8候选精确文件并记hash；全新owned tmpfs PG，无原卷，使用原conftest创建独占aos_test_*_ti4_test并原完整迁移至candidate162、原JWT/TLS测试issuer与真正低权cost配置链、通用Policy Store正反/跨Tenant/幂等回归。pytest保留完整native库readback后停止本Task容器，不以fixture真人代签或原预算批准；若迁移/测试失败先同handle/库只读对账，不另造简化通过声明。

完整复审r1：p2 SQL PASS已合法消费，仅局部；p1 NEED_EVIDENCE合法消费；p3/p4 response-format terminal失败保留raw，禁止手改JSON。补充r26仅证据文件：新owned tmpfs PG以项目标准aos_app schema owner初始化，调用原冻结conftest全迁移generator；SQLAlchemy只读catalog观察器记录原128guard在162 CREATEORREPLACE前后OID/Owner/ACL及body hash，结束抓native六角色/no memberships/caller无原表DML/七FORCERLS/immutable及deferred触发器/seal。实际原私有OIDC配置只读核600/700和SHA；在同一原已授权本机登录入口单次正常登录，token仅内存不输出不保存；真实token只用于authenticate_checker的READONLY身份验证，正常fixtureissuer session/current-member读，**绝不decide/revoke/consume、不预算批准**。fixture member setup只是测试前置，不声明原DB审批；不得使用真实JWT签署fixture预算。检查P/D/R/原policy记录全0、角色复位NOLOGIN并停止fixture。此证据不实现B保护文件加载器/真实credential配置，不给运营权限；补足A verifier与迁移物证后相同全8源码hash重新合法冻结复审。

consumer最后片段：新增严格consume DTO SQL验证、原proposal/approved Decision+issuerReceipt完整证明、同proposal advisory→proposal→decision/revocation→policy head FOR UPDATE→Budget/Provider/member锁序。current_source helper复用原typed/hash资料；明确目标必须已到生效时点且未过期。先consume Receipt(由SQL txid生成)再原policy INSERT/原head精确CAS，任何错误rollback；BEFORE original guard新pair分支再次完整核同TX Receipt/目标，旧cost pair原逻辑不改、Python generic ACTIVE拒绝不改。deferred constraint trigger于COMMIT核canonical目标与head/批准/无撤销/当前member/窗口，并禁止Receipt-only提交。历史consume只读核immutable canonical目标/原Decision+Receipt，不要求旧target仍current，也不把历史结果当新预算许可。正常写路径要求原cost_configuration trigger存在且enabled/绑定原guard，不以fixture替代表绕过。隔离source数据仅由setup建立，正常consumer实际低权role通过原trigger；真实JWT/预算同意仍B/C待验。原authority表和一般API不扩权、默认callerNOLOGIN，原卷不执行。

下一片段 decide/revoke：public DTO仍无actor；Store先独立catalog核验、原JWT resolver/唯一pin/currentMember观测，再调用仅issuer_call可执行的固定SQL函数。SQL只信这个独立private issuer TCB的actor，必须等于pin及proposal checker，不能信通用API/机器字符串。decide同proposal advisory→proposal→decision→source/Budget/Provider/member锁序，完整targetActiveHash/原Owner快照重核后写immutable decision+Receipt；拒绝也不发布canonical。revoke绑定原approved decision/hash、reasonCode；不要求已漂移的Budget/Provider恢复正常才能撤销，保留原human/member/完整proposal/decision证明和同advisory锁，撤销不能伪造新target/审批。任何重复key/hash只返回原immutable结果，不作为许可；consumer未来同锁核最新revocation。历史issuer reconcile只读核原request/actor/完整decision+Receipt，不把后续撤销抹成“旧批准未发生”，但返回事实不授权消费。native DB issuer TCB fixture只验持久化/权限/锁协议，不签假JWT、不是原真人真实批准或预算启用；C仍必须原真人实际OIDC验收。

本次完整 A 的下一实现片段是机器 propose 与其历史 reconcile（不是 A 的缩小交付）：源 helper 从原 policy head→Budget head→Provider head→唯一 checker member 按登记顺序锁定并核 canonical/hash/tenant/生命周期/显式窗口，只改 revision、未来 approval slot 和两组窗口。源授权允许原合同中的“policy窗口包含于authorization窗口”，不新增必须完全相等的门。生成 sourcePolicy/sourceBudget/sourceProvider snapshots，Store 在 SQL 返回后、COMMIT 前复用原 BudgetPolicyRenewalProposal 及原 Budget/Provider typed模型与 canonical_hash 再验。提案Hash及Receipt同事务持久化，不改任何canonical金融head/revision，也不制造Decision。重复同key同hash返回原 immutable提案；错hash conflict；历史reconcile只读核原完整快照及Receipt，不以 current head推进否定历史结果，未观察到结果不授重发。manifest扩充这些新函数及原hash/canonical/immutable/costguard，保留旧函数owner/COMMENT/ACL（仅登记的pure hash grant除外）。其余decide/revoke/consume和完整原子发布guard仍必须实现及非空三主体验证，不做partial Delivery。

用户要求开发过程中逐台比对原视觉效果。原稿根目录为 /Users/ddt/work/projects/ai_agent/docs/palantier/foundry/html；八台映射由 assets/workshop-shell.js 的统一导航核实，不以 html_back 或历史截图替代当前原稿。

| 工作台 | 原视觉稿 |
| --- | --- |
| 日常任务总控 | workshop-task-cockpit.html |
| 统一运营 | workshop-app-order.html |
| 内容与活动 | workshop-content-campaign.html |
| 达人邀约 | workshop-creator-outreach.html |
| 多媒体内容生产 | workshop-media-studio.html |
| 经营参谋 | workshop-analyst.html |
| 价格治理 | workshop-price-governance.html |
| 客户关系 | workshop-customer.html |

后续涉及工作台页面的每波 Loop，在真实浏览器验收环节加入以下要求：

1. 记录原稿文件哈希、实际 Web 版本、页面/选中页签、租户与真实状态、截图时间；原稿和实际页采用相同视口、主题及菜单展开状态。以 1280、1440、1920 三种宽度检查，明确记录高度；按实际变化补充窄屏、缩放、长文本与空/阻断/错误状态。
2. 保存并实际查看原稿及运行版新截图，形成并排对照；逐项核对导航和内容分区、信息层级、字体、间距、颜色、边框、卡片与表格密度、按钮状态、滚动溢出及焦点可见性。
3. 将视觉偏差与真实业务状态差异分开记录。原稿示例数据、可点击按钮或演示进度不得移植为真实业务事实；缺数据、审批、预算或权限时继续正确展示空态、阻断或禁入。不得为匹配稿件而开放受限操作。
4. 偏差登记为可定位问题，按批准方案最小修复，复拍同视口截图，核对交互与相邻功能；纳入独立 Prime 和 Delivery 证据。视觉合格不能替代自然经营首链、真人评审、安装恢复重装及连续观察。
5. 本 A 波当前仅合同/身份层开发，没有页面交付；此处登记持续验收约束，不宣称八台视觉审查完成。2026-10-14 已只读核实原稿八台导航，并在本地浏览器打开经营参谋原稿。后续全量截图和差异审查另行逐项登记，不复用历史验收结论。
