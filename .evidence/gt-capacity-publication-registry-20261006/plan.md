# 152独立根登记边界实施计划

基线AOS-001408 / m1 b9075431，Task gt-capacity-publication-registry-20261006，owner本thread，Scope四精确文件/目录与全部5未释放Lease无重叠，期限2026-10-07 12:00+08:00。遵守231完整首链/八场景与原publication计划，原FullSource/formalBoundary/publication/b90不因子任务进展退出。原Source/publication现有文件仍由原Task唯一写，151已占withdrawal，不覆盖。

两个已登记候选：R0独立private schema/角色/不可变文档与epoch地基（本轮开始）；R1锚定完整签名bootstrap→全根原文→实际部署与epoch登记，需要R0及受控anchor配置/原生密码学依赖。R2真实提交/rollback/replay/撤回竞争/原issuer边界及独立当前性回读，是本Task完整退出；R0空表/单测不交付FullTask。

## 原完整方案复习

原私有Source caller原批准/Owner/Provider/Evidence/withdrawal全部guard先完成，再新域root-policy epoch、文档、稳定account+Provider映射锁。注册写者只取新域，不逆向进入旧guard/License/Capacity。bootstrap签名由独立安装anchor的受控外部签发者批准，全部rawbytes/root整hash、publisher外部subject与专用dbrole/实际DB及允许doc exactrefs绑定；自由callerkey/verified/ExpectedDB不得授权。SourceIssuer没有Root登记/写/查询helper权限。当前原Source最终COMMIT TTL裁决仍pending，152地基或bootstrap也不授其签发/执行权。

## R0物理地基

两个独立NOLOGIN/NOINHERIT/NOSUPERUSER/NOCREATEDB/NOCREATEROLE/NOREPLICATION/NOBYPASSRLS角色：aos_capacity_publication_owner、aos_provider_capacity_policy_publisher。存在的保留名称必须检查所有flags、成员双向关系、当前DB现有owner或namedACL/defaultACL依赖，漂移拒绝，不删除角色/夺配置。Owner私有schema aos_capacity_publication_private，PUBLIC/runtime/issuer/publisher均无USAGE/CREATE。三原root pure profile函数只归owner，PUBLIC EXECUTE撤销；不复制parser、不给SQL helper当root信任。

五个空私有表：deployment_anchor（独立受控安装的公钥/部署/subject及anchor版本，默认无行）、root_snapshot（完整bytea/整sha256/数量声明，shape由R1原parser派生）、origin（完整bootstrap原文/signature及anchor+snapshot不可变关联，hash为主键，不将无上界revision缩为bigint）、root_entry（完整根ordinal、两canonical literal/codepoint身份、公钥/版本/时间及原rootbytes，scope/snapshotFK和full身份唯一）、registry_epoch（安装预建的稳定协调行、anchor与可空origin head、epoch，未来真实UPDATE锁与撤回协调，不懒建伪锁）。全部固定org-org/dev-project；RLS ENABLE/FORCE、唯一owner positive GUC policy，普通runtime/issuer/publisher无表/列/sequence权限。FK不可defer；默认无anchor/epoch/origin/root行，没有有效来源或可执行入口。

四immutable表UPDATE/DELETE触发器拒绝；epoch允许owner后继受限函数维护，仍不授他人任何UPDATE。未知效果不重发，后继幂等已知旧origin只对账。当前没有public SECD注册/Source prepare/commit/reconcile函数，无角色LOGIN开启/密码配置/anchor伪数据/C-extension全局安装，没有现库迁移或服务重启。升级只增本schema，不改变旧15表/5列与body；downgrade拒绝，禁止删除真实原文/anchor/epoch以“回滚”。

## R1与R2后继

在同一Task中补完整真实anchor初始化来源、签名验证依赖、实际cluster/database/受控host-port声明与bootstrap purpose/subject/专用角色/exactrefs/window/full snapshot hash校验；唯一受控登记函数从原bytes派生全部root rows、绑定immutable provenance，并更新root epoch/head。不拿数据库角色名称当外部OIDC事实；独立受控签名引导文档和安装身份必须建立真出处。root snapshot大输入从bytea存储/分块传输读取，整hash独立对照，一次完整解析，保留内联巨型HEX SQL OOM风险，不增加内存或截根。

测试：缺迁移/模块RED；R0真实测试PG catalog/空行/所有角色读写/schema/helper拒绝、owner positive与canary边界、immutable/FK及保留名称漂移；原Source/withdrawal/formal caller相邻检查十五表/五列原门。R1/R2实际签名正向与绕过/错部署/key/hash/subject/时间/RoleACL，真实COMMIT/rollback/replay与epoch writer-first/reader-first等才能完整Task Delivery。所有数据仅明确隔离测试库，当前真库与Provider/Host/worker off不操作。

## R0复审边界（2026-10-06）

模块和迁移只增加新private schema/两个默认NOLOGIN角色；复用原root parser常量。默认所有五表无行，不配置可信anchor，普通runtime/issuer/publisher没有schema/helper/表访问入口；四原文表禁UPDATE/DELETE，epoch独立保留给后继受限协调函数。隔离PG测试的管理员插入只是回滚fixture，不能充当正式初始化授权；FK/hash约束和权限测试不证明签名来源。R0不调用受控bootstrap或生产Root发布，R1/R2及Source最终COMMIT仍pending，保持Task ACTIVE，不写完整Delivery。无页面改变，本轮无适用浏览器验收；不操作当前库/服务/Provider/其他分支。

R0实测：缺模块RED1/7.04s；专项9/8.86s；首次相邻98pass+7旧151版本前提失败/154.99s；原formalBoundary计划先更新后最小改测试版本前提，最终新registry10+原formalBoundary96共106pass/148.19s，7既有warning。实际原trigger保护结果不放宽，Task仍ACTIVE。

## R1a签名引导登记入口方案

登记入口唯一三个参数（bootstrap rawbytes/signature/full root snapshot），不接caller key/verified/expectedDB/自由tenant。SECURITY DEFINER固定private OWNER，search_path pg_catalog；仅独立PUB角色EXECUTE+schema USAGE（非表/helper），默认仍NOLOGIN、无anchor和epoch行，源issuer无此入口。必须session_user=PUB、current_user=OWNER、双tenant GUC正向、PUB无inherit/super/createdb/createrole/repl/bypass及任何membership。角色名称不是外部OIDC证据：外部subject来自受控安装anchor及独立authority签署bootstrap的精确一致声明；正式安装主体核验/LOGIN配置另门，fixture只证明此签名与角色耦合协议。

先锁受控预建唯一epoch行FOR UPDATE，再查immutable anchor（epoch绑定anchor revision）；安装受控anchor target完整匹配bootstrap，实际current_database/pg_database OID/pg_control_system cluster id independently匹配；host/port来自正式受控anchor配置，不从容器5432逆推客户端映射端口。pg_control_system仅给私有OWNER该单函数EXECUTE，不给普通role/文件/网络权限。Bootstrap原16字段完整profile、原publisher/key/subject/anchor/window与整root hash全核；真C Ed25519函数需固定schema/签名/probin/prosrc/语言/immutable/strict/nonSECDEF/超级用户owner，实际库缺依赖拒绝。若依赖在安装时存在，仅给OWNER这单verify函数与schema USAGE；不在正式库安装扩展，不动原crypto权限。

验证全根完整原profile并一次派生全部root_entry行，整snapshot hash/数量由DB而非参数生成，原文与签名append-only保留。首登记epoch必须0/head NULL；受控初始化之外不懒建epoch，缺行不能伪锁。一次bootstrap hash引用若已为当前head，仅核验后对账返回；换body/旧head/篡改拒绝，不自行轮换或恢复撤回。Source策略/attestation/permit签发/最终COMMIT与当前消费者未开放。R1a不完整交付R1/R2；后继需受控安装anchor初始化证据、epoch撤回和真实COMMIT/rollback/replay/currentness竞争。

测试在既有固定none-network原生C实例BEGIN中安装新schema/角色与受控test-only anchor/epoch，SET SESSION AUTHORIZATION作为测试会话（明确非正式SCRAM/OIDC安装证据），actual bootstrap signature正向、坏签名/自由key/deployment/hash/subject/错误role/缺epoch拒绝与逐项完整根保存；事务ROLLBACK不留角色/行。当前应用隔离PG migration缺C不授权，原权限/触发器相邻回归保持。

R1a verifier owner前提纠正：原生catalog实测verify与schema均归既有独立aos_ed25519_owner（七flags全false、NOLOGIN），不是superuser。以该原安装身份+schema同owner+双方无membership为精确门；不为使测试过而更换原owner或开启superuser。保持固定C library/prosrc/strict/immutable/nonSECDEF检查。

R1a复审补门：known-head重复登记必须对账全部保存root行（count与全列EXCEPT），不是仅body/snapshot hash；增加受控管理员在fixture中TRUNCATE根行后同签名重查的拒绝反例。PUB不能TRUNCATE，该fixture仅模拟外部存储漂移。整体协议不授Source执行权限；后续最大域资源/提交竞争仍需验收。

R1a验收：原入口缺失RED1/5.91s；native首轮fixture未分号9fail保留，随后OID→numeric不可直接cast7fail改text::numeric；原crypto owner错误superuser前提2fail经实际catalog改为独立NOLOGIN aos_ed25519_owner。真实专项21/11.80s；相邻119/149.99s；复审补全已保存root rows对账、8MiB入口上界和pre-write时效后最终专项24/13.65s，7既有warning。两版专项及相邻验证范围分别记录；无finalCOMMIT时效保证。正式anchor安装/OIDC-SCRAM登录配置、最大域资源/实际提交与撤回竞争及Source完整发布仍pending，Task ACTIVE，无完整Delivery。

## R2a真实事务与固定epoch竞争验收

当前AOS-001410/bdec57b2，原Task同owner/四scope未变，Lease到7日12:00；其余5未释放lease不夺不删除。本轮精确文件：services/aos-api/tests/aip/test_capacity_publication_registry_pg.py及本证据目录。两个已登记候选：R2实际COMMIT/rollback/replay/currentness竞争（本轮），最大10000/8MiB资源域（后继）；不因正式安装尚未授权阻断此隔离验收。

固定colima-aos-a0v-test-only、none-network256MiB既有C镜像/label实例，只从无root schema的aos_test_ed25519模板创建随机aos_test_rootcommit_<uuid>库，Admin只在独立新库安装受控test-only anchor/epoch并COMMIT；原模板不改，新库和新域NOLOGIN角色保留供证据复查，不删除库/卷/backup，不对未知结果重发。Node不承诺实际publisher SCRAM/OIDC；SET SESSION AUTHORIZATION fixture只用于真实SQL session/角色协议，正式安装身份仍后继。

一例真实register返回后ROLLBACK，独立新连接核snapshot/origin/root行全零和epoch0/headNULL；随后真实register COMMIT，第三连接核全原文/hash/签名/所有根与epoch1/head一致，已知重复请求只对账不推进。两个psql会话保持打开并可查pg_stat_activity/pids，使用真实pg_blocking_pids证明固定registry_epoch锁：registrar-first时test-only管理员UPDATE epoch被阻，registrar提交后管理员提交epoch2；writer-first时管理员UPDATE epoch未提交，registrar被阻，writer提交后registrar拒旧签名。最后独立连接核原文仍保留、epoch2，旧原文不能再登记。

管理员epoch UPDATE只是模拟固定新域的失效事件，不代表正式signed root撤回API或批准。此次可证明SQL事务持久化/原文回滚与真实行锁协调，不证明final-COMMIT TTL（允许提前检查后延迟提交的旧缺口）、受控安装身份、最大域资源、完整Source/八工作台或自然首链。测试进程读取stdout/pid超时先同句柄对账；不在超时后另起相同副作用或自动重试。无页面变更不做浏览器验收。

## R2b完整签名最大transport资源域

仍同Task四scope，本轮测试fixture返回仅内存临时签名key给测试，不写日志或提交；新随机测试库中以真实签名bootstrap批准8190016byte/10000根纯canonical transport（明确非1MiB原File证据），保持原256MiB image，不增内存/截根。32KiB COPY hexparts→独立TEMP bytea→整sha256对照→一次完整注册；只给PUB临时输入表读取，不改永久root ACL。单次测试statement_timeout/客户端timeout90秒仅作为此大域实验预算，不改产品/全局配置。结束实际COMMIT/独立count/rawhash/epoch核对，失败保留库与原文、只读对账不重发未知效果；不得把小输入通过推及完整10000/8MiB域。若资源错误才做最小实现修复，复验同域及相邻；实际原File1200 expanded证据另门，不混称出处。

## R2b累计资源RED与最小修复方案

累计489中484pass/5fail：最大登记连接中断，随后4项crypto/profile测试命中恢复期；实际C cgroup memory.events oom=1/oom_kill=1，memory固定268435456，非disk再满。未知最大登记库先只读对账：origin/snapshot/root=0、epoch0/headNULL，明确未提交，不重发。原单项1/24.85s通过不能宣称累计稳定。

根因代码保留全量composite[] array_agg再unnest，不能spill，重复内存放大。最小修改仅私有register_origin：替换为一次完整root解析的MATERIALIZED CTE（tuplestore可spill），依赖RETURNING的snapshot→origin→root三个原文INSERT保持全事务原子；known replay同一次MATERIALIZED cache完整count/EXCEPT对账，不再构建array。函数局部work_mem固定4MB（非全局，不增容器RAM/不截根/不改接受域）；派生写完返回前再核窗口，过期异常回滚全部，本检查仍不是final COMMIT TTL保证。实际同10000/8190016完整域+既有28专项/原publication累计复验，所有失败保留，后续不把test-only成正式Source授权。

R2b修复累计仍RED482/489，oom_kill由1到2；未知库5ebb4d180a0c只读确认0/0/0/epoch0，仍未提交。停止通过次数推断；下一步只在新独立test DB诊断同域backend内存上下文和cgroup anon/shmem，观察本身只读，不重放原请求。原私有parser仍复用，正式DB不触及。

R2b final review: complete byte cursor + materialized registry parse verified in cumulative493/127.08s with7 pre-existing warnings. True10000/8190016 COMMIT retained in5300adc5a81c and independent hash/count/epoch proof; rollback/replay and both real epoch session blocking orders green. Fixed256MiB; oom4/kill3 unchanged through final suite. All previous failures/interrupted runs and read-only uncommitted reconciliations preserved. Source fields/function ACL/tenant gates unchanged. No full Root/Source Delivery: formal installation/SCRAM/signed withdrawal/final-COMMIT TTL/consumer still pending.

R3 a153 adjacent catalog reconciliation (AOS-001412): original unique m1 writer/Root Task scope still valid. First606 cumulative605passed/1failed because exact five-table inventory rejected the new planned private document table before inspecting its RLS/owner/FKs. Update only original test_capacity_publication_registry_pg.py to require exact TABLES plus explicitly declared DOCUMENT_TABLES, retaining every role flag/all-row RLS-owner and nondeferred FK assertion; no arbitrary extra tables or skipped checks. Actual a153/new doc matrices and full four-file regression required.


## R2c cumulative memory regression investigation
Document29 passed, final four-module cumulative618 has551PASS/67FAIL in268.29s. Full10000/8190016 root registration caused checkpointer SIGKILL with cgroup OOM6/kill4 versus prior4/3; remaining failures include database-recovery cascades. Isolated retained database aos_test_rootcommit_f3dfaca7e95a independently reconciled origin/snapshot/root=0/0/0 and epoch0/headNULL; template private schema0. No unknown registration resend. Current shared_buffers128MB consumes most fixed256MiB; do not raise memory or shrink input. Original parser retains UTF8 document and whole-array JSON after opaque row query starts, although subsequent validation uses original bytea only. Minimal proposal: release unused full document after array extraction and release the array variable after the FOR query starts; query owns its evaluated input, canonical byte cursor and all typed row checks stay intact. Publication-store file is covered by renewed original publication-schema Task until7Oct12; Root evidence/test own Root Task scope. Run exact failed maximal domain then all original full parser/canonical/late invalid and four-module cumulative; if peak still fails, retain evidence and diagnose further. No formal resources, deletion or broad config change. This is a proposed memory reduction, not a proven fix.
