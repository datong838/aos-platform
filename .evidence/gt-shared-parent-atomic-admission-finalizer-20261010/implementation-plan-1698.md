# 完整共享父风险原子准入与finalizer实施计划

Rules：231、原joint实施§3/§11.3、最小更改、单m1写者、未知效果不重发。Task10仅准备能力已官方交付，不再修改其scope。完整长程目标不缩小。

## 原始要求与新版本边界
一次真实准入COMMIT必须包含当前signed Source/身份/独立审批、精确两个父预算、全case四腿描述和cert、唯一Target Intent与Judge pending dependency、首个物理义务和不可变准入Receipt。外部Target/后继Judge在已提交准入后执行；Target实际结果是Judge后继依赖，不能在准入里伪造。所有风险保留并与原预算原算法共用；unknown/Source更新/到期不能自动返额或重新派发。

原准备artifact七个deferred检查使用无条件拒绝函数。完整新版本不能将该旧函数改为常真、关闭trigger、SET ALL或删原FK，不能把Task10的prepared_only row提升成正式Receipt。采用明确隔离的新版本入口和完整生命周期，原准备路径保持拒绝。新路径须复用原预算/Source/物理算法及核验核心，而非复制简化alg或另造fake来源；需要提取common kernel时，须在对应现有Task精确scope先登记计划，逐字验证旧生成SQL/已安装函数body hash、权限和所有相邻行为不变。新版本计算必须纳入旧未决风险；无完整切换、历史映射和独立签名来源则禁入，不能以表空推断正式权限。

## 精确文件与接线
本Task产品scope：services/aos-api/aos_api/aip_shared_parent_atomic_admission.py；services/aos-api/tests/aip/test_shared_parent_atomic_admission_pg.py；证据位于本目录。两文件已创建原fact接线及原生边界测试；完整准入、版本账本和提交结束门尚未实现，不把此增量当整Task交付。
支持接线必须逐文件回读既有Task归属：aip_physical_capacity_occupation_authority.py（当前回读属Task1）、aip_physical_capacity_occupation.py（原Task1）、预算/模型Owner及contracts（对应原Task），不能创建重叠Lease或在本Task冒写。需要新迁移时先核代码head和迁移分配，再单独登记该精确文件；不重写已发布版本，真库仍只读。

## 必须完成的流程
1. 当前原Source签名/安装事实、两原真实批准request和parent hold同native caller/xid/pid；费用fence→物理account update→三桶固定序，禁止callbacks/普通Task替代Eval。
2. 明确新版本kernel与保存模型及old unresolved兼容切换；全请求父上界与物理累计不重复持有，第一Target Intent唯一，Judge等待真实Target结果，非执行签名/描述不能当当前准入。
3. 全manifest/cert/identity锁先取得，保存准入可信Receipt及所有实际effect。完整event fixedpoint/RI/C verifier/索引比较/函数和native部署来源全部精确冻结，不能以部分catalog代替真实queue。
4. 所有实际等锁与当前性读取先于最终DB clock决策；结束入口仅一次真实COMMIT，early SET/多结束命令拒绝。决策点不是WAL/ACK；若需实际COMMIT期限，则定义提交后可信确认和超时非执行/风险保留协议，不能修改需求或事后假rollback。
5. 独立连接在首次synthetic dispatch前核唯一已提交Intent/风险/Receipt；原worker unknown journal不重发语义必须保留。后继native Target结果consumer核独立COMMITTED origin/当前Root/head/实际transportUsage，Judge须组合v3签名与exact输入门，最终发布/currentResolver同证明。
6. 原生全准入positive、每节点故障rollback、hash/replay/不同caller/canary、读者先/写者先撤回与期限竞争、early COMMIT/SET、后续触发等锁跨期、未知提交只读对账；原预算/physical/正常Content邻接、适用浏览器、方案代码复审、Delivery/精确提交/上下文。

## 当前选项及实测第一步
候选一完整新版本准入/finalizer：用户已批准设计/隔离实现，依赖上述核内复用与完整结束门；本轮选择原生目录RED，确认旧七个拒绝门仍完整、候选新入口缺失，明确版本差距后推进kernel文件级接线。候选二正式native部署/Root信任：已登记，但需要正式签名来源/独立发布资料，不能用实验bootstrap替代。二者均不触达当前真库、真实Host/Provider或旧12Run。

## AOS-001715 维护后完整新版本接线调查
原维护执行已知终态、当前159真库恢复只读。本Task同owner租约已对账续期，无重叠，无Delivery。候选一为完整新版本准入/finalizer，已批准隔离实现但必须复用原可信facts并计入全部旧未决风险；候选二正式native部署/Root来源，依赖独立正式签名不执行。选择一：新增本目录admission-kernel-binding-1715.py/json，静态生成精确原SQL并抽取CREATE表/INSERT/UPDATE/SELECT锁、实际deferred guards、容量计数与继承需求；核原14生成器对1699beforeimage逐字相同，原七拒绝门保持。禁止用这份静态清单证明native queue/完整准入GREEN。产品两文件仍未创建；本步不访问数据库、不安装函数、不触达Provider。下一实施以显式新版本tables、旧风险兼容mapping及完整结束通道为同一个交付包，不能通过替换prepare或关闭七guard获得正向。

## AOS-001716 原生安装范围对账
历史read-native-capacity-kernel-r2-1699在确认Judge旧per-case debit函数存在时失败；实际保留库仅安装完整shared准备所需plan_risk/shared_description/target_call/target_occupation四producer及七个原拒绝trigger，两个旧per-case debit均不存在。禁止为修测试安装旧逐case费用路径。新增native-kernel-scope-readback-1716.py/json，仅SER READ ONLY对四个实际生成body、Owner/SECURITY DEFINER/search_path/ACL及七个拒绝body逐字核；缺失legacy两个函数明确记为未部署，不能宣称已安装body验证。原生回读通过后接入新version kernel，不降低full admission目标。

## 新准入入口原fact接线（本轮产品增量）
精确新增services/aos-api/aos_api/aip_shared_parent_atomic_admission.py及tests/aip/test_shared_parent_atomic_admission_pg.py。新固定签名public.read_shared_parent_admission_original_facts(bytea,jsonb,uuid,text,text,uuid,text,text)仅委托原capacity_occupation_plan_risk_fact，不复制原Source/申请/审批/hold/cost算法，不写legacy准备账本、不签名、不COMMIT。新SECURITY DEFINER函数仍固定原physical Owner/search_path，拒PUBLIC/runtime直接EXECUTE；固定occupation登录、runtime当前role、SERIALIZABLE/UTC/origin/org-org+dev-project校验在原fact调用前。新trusted完整admission后续从原Owner内部调用；仍须全case/cert/版本风险账本/commit-end原生完整实现，不把此fact入口交付为完整Task。RED先缺产品module；GREEN验证native显式DDL仅在原保留test库事务中创建、元数据Owner/ACL精确、恶意session/canary拒绝并整体rollback，原七guard及四producer全量body不改。真库159仍只读，不注册服务、不新迁移、不开启业务。

本次实现仅完成完整新准入的原fact接线：首次native测例在SET ROLE先失败，确认occupation登录无runtime membership，不为测试扩大权限；更正为真实admin边界拒绝及no-elevation矩阵，未声称authorized-caller canary字段单独验收。新7项及相邻共82通过；所有新DDL rollback且原native四函数/七guard/ACL保持。新函数无runtime/PUBLIC grants、不自动安装、不写旧账本。全准入正向、版本账本/证书复用/结束门仍待下一实施，Task无Delivery。

## 复用原证书核（支持Task gt-shared-certificate-validation-kernel-20261010）
支持Task已将原nativeC requirement及完整set/Root锁/v3 claim/signature/time块提取为固定零参数helper，13条旧SQL和三native body/ACL全部精确保持。主Task新module新增shared_parent_admission_certificate_validation_sql，按原次序组合两helper，供完整version入口在真实doc/items/Source/父预算/原Issuer委托下调用；不建新的crypto verifier、不参数化schema/Root、不复制claim判断、不自动授physical Owner VERIFY。新增测试确认新构建确实消费同一两个helper；不把SQL片段视为准入receipt或授权。下一仍完整version风险账本及可信doc/Issuer narrowdelegate/endchannel。

## 原完整描述核接线 AOS-001718
原physical Task gt-atomic-model-admission-20261008按exact scope提取全部manifest/caseSet/独立两父预算/每case/Source-account-provider两leg完整检查，原14 SQL生成器逐字保持；主Task从原physical module调用同一零参数核，作为新version trusted风险/描述建立的固定检查片段。不能把普通JSON或旧prepared_only行升级成可信doc；新版本schema/保存来源/窄Issuer委托/原风险兼容账本/完整endchannel仍需同一完整交付。

## 原生可信来源构建入口 AOS-001719
新增本Task module内固定build_shared_parent_admission_origin(bytea,jsonb,uuid,text,text,uuid,text,text,uuid,jsonb,text)，无JSON facts/风险/描述输入。委托原fact入口→原Source fact→复用原风险body核→派生内存risk的immutable/hash/两request→原完整manifest核→新版本nonexecuting origin文档→原fact再次读取比较。原临时risk变量仅用于复用校验，不读写prepared表，无DDL/Receipt/dispatch/ledger/COMMIT。生成doc绑定session/caller xid pid和原完整risk hash；没有完整物理/费用/证书/历史义务/结束门不变为可执行。原physical Owner/search_path与runtime直接禁EXECUTE仍保持，原fact依赖先安装仅在native测试rollback中。native SQL编译/Owner ACL/错误session拒绝及回滚absent核验；真实完整正向来源必须原正式创建/独立审批签名fixture，不能mockfact来宣布正向。

## 原生来源正向验收 AOS-001720
独立fresh实验r1~r4均未完成新origin正向，具体过期harness窗口/严格原Judge路径/两层helper复制/SERIAL快照之前DDL原因保留。r5新origin正向及5negatives完成，但相邻helper缺失令整测试失败；不claimr5整包GREEN。r6修复复制完整原helper，保持原150s新审批函数字节不改，fresh保留DB全测试1PASS83.99s/8warnings；独立SER READ ONLY证明new2bodyOwner/ACL/noRuntimeGrant精确，legacy risk/description0，原caller aborted，两原hold0。正向Source/批准由原producer和真实签名形成，但测试Root不作正式provenance；无新ledger/Intent/certdelegate/fullendchannel/actualadmissionCOMMIT或业务首链。

## AOS-001721 原生完整证书集合内部接线
本步是完整新版本准入的内部构件，不代替可信保存/完整风险账本/Intent/end-channel/真实COMMIT。原native-positive库只证明Source与两个父预算，不含原certificate verifier；记录缺口，不安装旧未知结果或将该库当完整证书正向。
精确修改 services/aos-api/aos_api/aip_shared_parent_atomic_admission.py 和 services/aos-api/tests/aip/test_shared_parent_atomic_admission_pg.py。新增关闭的Issuer SECURITY DEFINER入口只接受rawSource/exactRef/两父hold/request/hash/plan/manifest/hash/完整原始证书bytes，不接受可信doc/risk。在同一原occupation SERIAL UTC caller中调用已有新原生ORIGIN，取得doc和descriptionHash，再逐字复用原C verifier要求及全部v3 claim/签名/Root锁/当前性。结束前重取原生doc，要求完全相同，再复用完整claim检查，不能将检查时间宣称WAL期限。
新ORIGIN仅新增显式EXECUTE给既有Issuer Owner，非runtime/PUBLIC；新核验函数Issuer Owner所有，PUBLIC/runtime/Provider issuer无EXECUTE。不改任何原函数/旧七拒绝门/VERIFY权限；物理Owner不获VERIFY能力。全部SQL仅显式artifact，无导入安装、无表写、无签发、无Root创建、无执行权限。后续真正保存和最终入口必须使用此原生核验再计入旧风险；不能从客户端JSON信任，也不能由这个返回值获得准入Receipt。
RED：新入口artifact不存在；GREEN：保留原库事务内原生DDL/Owner/search_path/ACL/恶意caller早拒及rollback复核、相邻专项。完整真签名集合的原生正向及持锁期限竞争须另在新test-owned fixture安装原证书artifact后验收，未执行不宣称通过。测试artifact中函数编译不能代替调用签名验证。

## AOS-001722 完整原生证书接线验收
新隔离库aos_test_f675cc1af2ea_ti4_test实际原Source/两独立申请与父预算、预发布test Root、4条真实签名和7证书负门，原Source整体相邻/cleanup共1PASS135.30秒8warnings；独立只读回读函数body/Issuer闭权限/物理Owner无VERIFY/caller aborted/两hold零残留。r1-r6全部保留，r6局部矩阵通过但完整相邻RED明确不算整体GREEN。R7去掉1720已完成来源负门重复，没有删证书矩阵或Source相邻、没有放宽审批/身份/Root deadline；只修test fixture，不改产品。下一步仍为同完整Task的native可信保存/旧新未决risk账本、唯一Target Intent和Judge actual dependency及end-channel实际COMMIT，未交付整Task。

## AOS-001723 可信原生来源保存与未完成结束门
修改仅 services/aos-api/aos_api/aip_shared_parent_atomic_admission.py、services/aos-api/tests/aip/test_shared_parent_atomic_admission_pg.py。显式新private schema归既有Issuer Owner，关闭PUBLIC/runtime/Provider issuer；可信记录保存四签名和原生来源/hash、精确两hold/account/caller xidpid。固定原始参数入口由Issuer SECURITY DEFINER先调用当前新证书核验（仍原Source/原审批/完整v3 claim），派生body及全部绑定列；不收可信docJSON、不存rawSource身份包、不增加VERIFY权限。INSERT-only，重复同plan同内容同caller返回同记录，不同内容/caller拒绝；RLS FORCE、不可变UPDATE/DELETE/TRUNCATE，基于原NOLOGIN Owner与关闭ACL。
新记录只是same-transaction awaiting_full_admission候选，不是完整准入Receipt或已承诺physical obligation。新deferred结束触发器固定依赖本schema.require_complete_admission(uuid,text,xid8,integer)，当前不存在时明确拒绝COMMIT。未来该精确callee必须是原physical Owner、SECURITY DEFINER/固定search_path/void，且完整原预算、旧新未决全局物理风险/唯一Intent/Judge pending dependency/全部native effect+RI/真实结束协议完成后才能显式安装；缺失不降级，不用caller setting或新签名替代。旧七prepared拒绝门完全不改；新guard不是允许空manifest/空表提交的捷径，也不把决策clock当WAL期限。
RED新保存artifact缺失；先原生事务内DDL/Owner/ACL/RLS/不可变/deferrable元数据和恶意caller拒绝及DDL回滚；再新保留库内实际原Source/两批准hold/四签名保存、同caller回读与真实COMMIT拒绝/独立aborted/零保存及hold。完整联合准入COMMIT/旧新风险计数仍未实现，全部Task退出条件保留，不写Delivery。不触正式DB，不自动安装，不涉及浏览器页面。

## 1723-r1 原生截断拒绝断言修正
332项相邻通过。r1真实保存后UPDATE/DELETE被不可变门拒绝；TRUNCATE在待deferred事件存在时由PG原生55006先拒绝，测试原只接受42501而失败。产品无需放宽或改动。r2新隔离数据库/新申请/新签名，断言精确55006与pending trigger events；后续原Source相邻及真实COMMIT缺失结束通道拒绝保留。原r1未知数据库结果仅只读，不重跑。

## 1724 下一波 Owner 交接门
独立SER READ ONLY新保留库确认physical Owner对Issuer pending schema无USAGE、表无SELECT，完整结束入口不存在；不能假设后续physical endcallee能读取该表。下一最小步骤先设计固定可信lookup/精确函数委托：只读取同当前native caller/xid/pid与plan/hash的已原生核验记录，不授宽schema/table权限；再复用原account fence和费用桶顺序，联合旧未决风险/新risk/唯一Intent/Judge依赖。必须逐字冻结新查找函数与闭ACL、纳入全部event/RI/真实COMMIT测试，metadata门不授执行权限。正式Root来源为第二已登记候选，隔离test Root不解该门。

## 1724 固定跨 Owner 查询实施
精确产品两文件不变。新增 public.read_shared_parent_pending_origin(bytea,jsonb,uuid,text,text,uuid,text,text,uuid,jsonb,text,bytea,text)，Issuer Owner SECURITY DEFINER/pg_catalog。仅显式GRANT EXECUTE给既有physical Owner；PUBLIC/runtime/Provider issuer仍关闭，无schema/table权限扩张。接受原raw Source/exactRef/两hold/request/hash/plan/manifest/hash/完整canonical certificates和精确pending hash，先完整原生CERT核验，再FOR SHARE读取pending表；派生预期body并核caller xidpid/hash/tenant/account/hold，等锁后重复完整CERT核验且结果完全相同。返回可信pending候选，不写任何risk/Intent/receipt、不插入不存在记录、不授执行、不改变旧七guard或现有SQL输出。
RED新增函数不存在；GREEN原生DDL/Owner/ACL/RLS权限不扩张及恶意caller早拒、完整新鲜Source/两hold/四签名同caller保存后physical Owner固定代理实际读取；hash错/plan错/坏证书/普通runtime拒绝，真实COMMIT仍拒绝缺失完整结束门、独立回滚readback。所有原生正向在新保留实验库和新审批内执行，不复用旧效果。

1724 lookup-r1测试安装误用不存在api别名且漏lookup artifact，19.07秒NameError终止，保留新库及失败；仅修新r2测试prepare的admission别名与显式artifact安装，不改产品/审批/Root/TTL，生成全新隔离库与审批，不重放r1。

## 1725 首 Target 物理义务及旧新计数
精确两产品文件新增显式physical private schema，Owner沿用原physical Owner；所有表/函数闭PUBLIC/runtime/Provider issuer权限，FORCE RLS/正向scope。不可变首Target obligation按plan唯一，保存精确pending hash、首case、原target hold/account/token上界、caller xidpid，无TTL清零或release接口。固定raw参数入口先原account guard实际version UPDATE，再精确Owner lookup完整当前原Source/两hold/四签名；计数旧prepared_parent_debit与新义务同physical account，复用原_physical_call_capacity_guard_sql('target')，不改原SQL、不把全case父上界重复扣费。此前取得原费用fence/Source/budget顺序仍由完整producer保证，本内部构件不能替代该顺序验收。
重放仅同plan/hash/case/hold/account/tokens/caller原事务相同；已有义务不重新计额，冲突拒绝。新记录仍pending_full_admission，无Intent绑定/实际执行权限；新deferred结束门明确缺完整finalizer就拒绝。完整旧writer清单/签名cutover/未知义务映射、窗口token语义、唯一Intent/Judge依赖与真实结束协议仍属于整体退出条件，不因这张表或局部计数通过而授权正式切换。首case token从原fact取得而非caller supplied。
RED artifact缺失；GREEN原生DDL闭ACL/Owner/RLS、admin拒绝、原入口SQL字节不变、相邻；另在全新Source/审批/四签名实验实际创建并重复首义务、独立实际COMMIT拒绝/义务与父hold零残留，未来完整并发/全窗口矩阵保留。禁止授正式权限或关闭旧七门。

1725元数据相邻333PASS1FAIL：admin调用到缺失原account guard，原生UndefinedFunction；新增入口在任何Source/account写前先拒绝非occupation/runtime/SER/UTC/origin/正向scope上下文，原有效native调用仍复用原guard，未以mock或跳过缺失依赖获得正向。已启动r1使用冻结前版本，终态后按bodyhash区分，不用其证明最新新增早拒；不修改运行中fixture或重发旧效果。
1725相邻r2在实测fixture运行时333PASS1FAIL：原拒绝角色测试观察到cluster级occupation→runtime临时测试membership，不能把不同DB误当独立全局角色。保持原测试不变、不撤销运行中fixture角色；等待当前唯一实测终态及角色恢复后串行重跑相邻。后续所有共享此cluster身份的实测/元数据测试串行，禁止并发污染。

1725初始义务r1：两实际创建/重放及缺结束门COMMIT拒绝通过，但原Source后续相邻和cleanup真实到期RED，129.75秒；安装body为新增早拒前版本，独立读回按精确旧body区分。新r2保持Source全相邻与cleanup、原TTL/审批/签名不改，仅不重复r1已局部验收的第二次义务重放，单次义务正向后实际提交拒绝再跑全部Source相邻。旧r1不当完整Green，测试排序节省重复来源核验不删除业务相邻或放宽期限。

## 1727 唯一首 Target Intent 与 Judge 等待依赖
产品scope原两文件；支持Task仅提取原physical_authority两个零参数共用片段，原14 SQL字节不变。新physical private表target_intent绑定initial_target_obligation的plan唯一，intentUUID唯一与(request,case,attempt=1)唯一；judge_dependency绑定精确Target Intent/hash、plan唯一且judge UUID独立。每表闭ACL/FORCE RLS/不可变、native deferred结束门。
固定新入口使用完整rawSource/两hold/request/hash/manifest/certs/pendingHash/obligationHash、原Suite raw和input raw及两Intent UUID。原CASE_FACT核当前真实Suite/Contract/具体首case，复用原输入bytes核；同caller original obligation/hash/plan/account/hold校验，复用原Target权威字段。写入新Target schema及Judge等待协议、原期望artifact，没有实际Target result/Judge input，也不再次扣父预算。唯一性/重放要求同caller、body和hash精确一致，不同Intent或请求case重复稳定拒绝。写后再通过固定Owner lookup完整Source/两审批/四签名当前性，任何不一致整事务拒绝。
这仍不是完整COMMIT：完整新旧风险/窗口/unknown切换、原唯一Intent外部producer/consumer兼容、全部event/RI最终检查和单一可信结束通道仍须完成；新功能不开放runtime权限、不替换原七guard。先RED新增artifact缺失→原14beforeimage字节保持+新原生metadata/ACL/admin拒绝→新鲜Source两审批四签名+实际Suite/input正向Target/Judge依赖与故障/提交拒绝/独立回滚。共享cluster角色测试全部串行，不放宽旧TTL或删Source总体相邻。
1727写入顺序细化：Target原CASE_FACT/输入后创建Target唯一行，再固定Issuer lookup验证完整4证书并取得原Judge facts；随后Judge唯一/FK写入。Root/head/key已有同事务SHARE锁，最后用原完整FUNCTION重读Source/两hold/所有case原facts并要求完全相同，DBclock校核此前原C核已验证且被Root期限上界约束的全部cert validFrom/Until。没有授physical Owner C verifier、不缓存客户端currentness、不以元数据门授准入；对真实等待跨期与同事务Root/Source变更完整负门仍需后续整体矩阵验收。新结束门仍不存在。

### 1727 fresh native r3 evidence refinement
r1 missing test-only certificate helper, r2 full original chain Source expiry RED retained. r3 keeps the original entire test and unchanged approval/Source deadlines; persist component proof at actual rejected COMMIT before subsequent original adjacent cases so partial component result is independently reconcilable. Whole fixture result remains separate and cannot be promoted from component PASS. No formal writes or old attempt replay.

### 1728 separate fresh Source adjacent acceptance
Original occupation test line320 invokes added shared Source trial before opening a distinct original ordinary caller (line324). r3 component actual native Intent/dependency and rejected COMMIT/readback passed, but stacked work exhausted initial Source consumer/supplier currentness during later old checks. Next independently fresh Source baseline preserves original entire node and all old negatives/cleanup with integration hook disabled, no product/test-body modification or TTL increase. Component and baseline use separate fresh authorizations; do not relabel r3 whole RED as PASS. This is adjacent regression, not full shared admission or old replay.

## 1729 完整终门原始权威材料保全
复习231/原joint§3/栖月汇从可售→可买→可履约→可复盘产品边界；full ending必须重读原权威而非仅认派生snapshot。现有pending origin并未保存p_raw，固定plan/hash/xid/pid结束门无法还原原Source consumer/auth deadline。两个已登记候选：完整终门raw authority handoff（当前完整Task批准隔离实现，依赖现有pending/Issuer核）；全物理窗口/old unknown cutover（同Task，依赖完整结束及正式历史映射）。本轮先前者，完整业务目标不缩小。
产品精确两文件：services/aos-api/aos_api/aip_shared_parent_atomic_admission.py；services/aos-api/tests/aip/test_shared_parent_atomic_admission_pg.py。追加独立artifact，不改现有fact/origin/cert/persist/lookup/obligation/Intent SQL及原14生成器。固定Issuer private end_authority表plan唯一FK pending；仅存消费packet bytea及server-derived绑定body/hash。_consumption_packet原生成器只输出protocol/tenant/sourceRef/authentication(consumerSubject/issuer/audience/expiresAt)，不含bearer；显式闭字段/canonical/大小核防止意外存credential，多余字段拒绝，不改变原Source认证权限。body从原已验证pending derivation建，绑定原SourceRef/raw SHA256、pending hash、两hold/request/hash、manifest hash、caller xid/pid。canonical certificates从原pending中的byte-exact canonical JSON重建，既有certificateSetHash核验不变；所有身份/审批/Source/Root/证书deadline沿用原值，无refresh/TTL改写。
stage_shared_parent_end_authority仍接受原完整13参数：先固定READ_PENDING全原核→插入immutable native材料→samecaller精确重放→再次READ_PENDING全原核等锁后重核。不自动插入pending，不借旧prepared风险行。新表FORCE RLS/Issuer Owner/无PUBLIC/runtime/provider/physical schema-table权限；BEFORE binding核native caller/正向scope/字段/body/hash/raw/schema和原pending。UPDATE/DELETE/TRUNCATE拒绝。deferred仍使用固定现有Issuer require_pending_completion，新增material hash为已登记typed node hash，未来完整结束门须从固定private已验证记录识别对应plan节点并验证全包，不能把此hash当独立准入receipt；终门当前仍缺失，实际COMMIT继续拒绝。
read_shared_parent_retained_origin(uuid,text,xid8,integer)仅GRANT给physical Owner，无raw caller输入、无runtime权限、无schema/table grant。先native八上下文+当前xid/pid→锁pending/material并核body/hash/raw/关联/旧pending→从存的Source packet、native body及pending原manifest/canonical cert重建固定13参数→调用原READ_PENDING完整验证。返回当前核验pending+material hash、不输出packet、不生成Receipt/Intent/执行许可。未来完整finalizer调用该固定窄门后仍须全physical/risk/window/cutover/events/RI/一次结束协议，不能以本增量实现空门或关闭旧七guard。
验收：RED新增DDL/入口缺失→原生metadata/ACL/RLS/管理员与canary/no-row拒绝、旧artifact byte exact→全新原Source/两批准/四签名真实stage/固定read/坏hash或caller/私表读及篡改packet负门/实际COMMIT缺结束拒绝/独立aborted零pending-material父hold回读；独立fresh原Source相邻全节点保持，不堆叠到期窗口、不重发任何旧attempt。未部署SQLartifact无适用浏览器，不以页面/单测当首链完成。

1729 r1新retained组件Stage/固定read/四negative/实际COMMIT拒绝及独立aborted零材料父hold通过，后续原Source相邻和supplier cleanup到期RED保留；不同Source独立原回归57.68s证据仍适用且原14/新既有7SQL组字节保持。r2新Source/新审批/新签名，补实际存在材料行UPDATE/DELETE不可变拒绝及合法native调用方切dev-org后固定read早拒，保留全部原试验流程与原TTL；无原结果重发。

1729 r2独立回读：保留库aos_test_9fcf64cfee71_ti4_test，7项实际负门（含合法caller canary、既存材料UPDATE/DELETE）与四签名、精确原生函数/ACL、实际COMMIT拒绝、aborted零pending/material/父hold及角色恢复通过；外层Source/cleanup因到期整轮RED，不能升级为全包GREEN。累计325通过，旧7artifact/原14SQL不变。独立模型review r1因返回Markdown fenced JSON被官方严格解析拒绝，保留原transport，不伪装已消费；r2为新纯材料请求，无执行权。

## 1730 原初调用材料闭合方案（编码前）
候选一为完整终门Suite/Input原字节重核，候选二为全物理窗口/历史unknown切换；先做前者，后者依赖完整结束通道及历史映射。
精确产品文件仍仅 services/aos-api/aos_api/aip_shared_parent_atomic_admission.py、services/aos-api/tests/aip/test_shared_parent_atomic_admission_pg.py。新增独立initial_call_authority artifact，原8组SQL逐字不变。物理Owner private表存原Source packet/Suite/Input bytea；Source用已存在闭字段核（不存bearer），Suite/Input原生CASE_FACT与input核复用INITIAL_INTENT，不猜canonical恢复原字节。绑定plan/pending/obligation/TargetIntent+hash/JudgeDependency+hash、三原字节SHA256及caller xid/pid。plan唯一、两Intent复合FK、同scope FORCE RLS；无runtime/Provider表和函数权限，immutable UPDATE/DELETE/TRUNCATE，deferred仍同既存完整结束通道，不能单独COMMIT。
固定stage接受原18参数，先原INITIAL_INTENT全部原核和两行幂等绑定，再新READ_RETAINED完整证书/Source当前性，server派生材料body/hash、存三bytea，后重复原核。固定read仅plan/hash/xid/pid：锁已有材料和通过FK保证的两Intent/obligation，核三字节hash与native两Intent/hash及caller，然后READ_RETAINED重读pending，从原facts/manifest/cert与材料重构原18参数，调用同INITIAL_INTENT再比精确native两body/hash。原INITIAL_INTENT可执行INSERT ON CONFLICT，但已存FK及原ID保证只能原同行精确幂等，不生成新ID/新Intent；材料read不接受caller原始facts。返回复核两Intent/hash及material hash，不返回原字节。保留原整个风险/物理窗口/事件RI/历史unknown/full ending缺口，不安装空终门、不授执行权。
RED artifact缺失；GREEN原生DDL/ACL/RLS/复合FK/管理员拒绝+回滚、原8 SQL byte image；然后新鲜Source两审批四签名真实stage/read和原始字节篡改/坏caller/坏hash/私表拒绝/既存不可变/实际COMMIT拒绝+独立aborted零行。metadata和Source串行，期限不改，整轮Source若到期继续保留RED。未部署artifact无浏览器验收条件。

1730 metadata r1误用旧artifact函数名、r2发现Judge无复合unique；均保留失败。调整为Judge原PK单列FK+BEFORE native hash绑定，Target沿用既有复合FK，不新增或修改原表约束。这样仍三FK、两hash原生核验，旧artifact字节不变。

1730 native r1在stage内READ_RETAINED原Source到期，未取得新增组件正向/COMMIT证据，保留aos_test_0f081ecfdac3_ti4_test及原Source teardown RED。r2全新Source/审批/签名，不重放；删夹具中上轮已验收的7项retention重复负门，仅做本轮原字节保存/固定重读及3新negative；原product核与外层Source测试及TTL均不变。若仍到期，登记真实路径耗时，不宣称组件PASS。

1730实际r1/r2均未完成新Stage正向，分别原Source expired/current consumer门拒绝，不能仅凭19原生结构+326累计GREEN宣称成功。两新保留库原生body与role恢复、initial材料/obligation/Intent/dependency全零已独立回读。下一项不是继续堆叠重试：在新fresh fixture逐段记录BEGIN/END/elapsed和原deadline，再评审整体pipeline重复重核，保持旧8artifact、原期限和等锁后全重核，不用轻量stub绕过full ending；当前新增artifact仅未部署WIP，无完整Task Delivery。

1731下一步实际测量：新隔离fresh attempt initial-call-timing-1731-r1，仅包装已有test-owned公开调用记录函数名、UTC开始/结束耗时及单行拒绝码，不记录参数/Source packet/credential、不修改产品SQL或原TTL。沿用r2全部本轮路径与原外层试验，结果独立保留；接续只poll本进程，不重发。

## 1731 基于实际耗时的 pending 窄门顺序修复（编码前）
真实timing fresh原生结果：origin3.43s、persist14.28s、end_authority29.07s、retained lookup14.46s、obligation29.02s；initial call在19.73s后被原current consumer门拒绝。静态展开stage26个plan fact出现位置为上界，不当实际次数。下一已登记候选一是窄门锁顺序修复（当前完整Task，隔离artifact）；候选二全物理窗口/unknown切换仍依赖whole ending。
仅修改 services/aos-api/aos_api/aip_shared_parent_atomic_admission.py 的未部署 READ_PENDING artifact；tests/aip/test_shared_parent_atomic_admission_pg.py 既有native矩阵复用。原已发布迁移/physical七拒绝体/原14SQL生成器不变。此前新8组byte exact是增量保护检查，不将其理解为禁止在证据证明缺陷后修复本Task未部署窄门；本轮允许且只允许READ_PENDING这1组生成体有意变更，另外7组与ACL/Owner/signature/table权限精确保持，记录before/after差异。
READ_PENDING只读且无任何业务写入。先原八context与cert大小门→native pending plan FOR SHARE→核同caller xid/pid、pending hash及canonical body、tenant、两父hold、cert原bytes/hash/state/false→取得锁后只调用一次完整原CERTIFICATE_SET→核原origin/两account对native pending精确一致→返回原同一doc。锁前那一遍完整重核没有产生授权、锁后已有更强完整原核且原CERTIFICATE_SET内部保留before/after全部Source/父预算/Root/head/签名/DBclock检查；删除的是无效果的重复调用，绝不缓存currentness、跳过等锁后重核、延长期限或生成准入COMMIT。由于没有中间写入/回调，先锁不可变pending再验证原authority不引入部分提交；锁排序风险需native fresh与等待/撤回后续完整矩阵保留，不宣称已全过。
RED使用已完成fresh timing-r1原实际currentness拒绝，不造新的镜像单测。GREEN19原生权限/编译/caller/RLS/rollback+326相邻；fresh同一路径带timing正向或真实RED并独立读库/精确body/四签名/全零回滚，复核整个Source结果，不凭结构GREEN授执行权。

1731 beforeimage基线现为9组（含上一波initial_call），实际仅READ_PENDING一组变更，另外8组完全相同；原14与旧physical7拒绝体未修改。新fresh实测end_authority14.51s、retained7.27s，相对独立上一fresh的29.07s/14.46s减少重复工作；尚未凭此宣称整波通过。

1731 fresh postlock r1：保留库aos_test_6142b10202c2_ti4_test，新initial call实际Stage24.17s/固定read15.58s正向，原输入篡改、错material hash、runtime私表读3negative以及实际missing-end COMMIT拒绝独立证据通过。native7函数body精确、4真签名、原caller aborted、全部材料/两Intent/obligation/原两父hold零、旧test角色恢复已独立回读。外层旧Source after-component及supplier cleanup到期RED保留；完整admission/Task/正式Root未通过。原Source独立fresh整体57.68s历史证据原文件哈希仍相同，不重复旧验收。

## 1732 原生窗口身份及旧/新未解除占用核算（编码前）
已登记候选一完整physical/window计数，候选二旧submitted/unknown切换正式映射；先实现同Task隔离窗口记录，旧无合法history不得伪造导入。精确产品目录仍 services/aos-api/aos_api/aip_shared_parent_atomic_admission.py 与 services/aos-api/tests/aip/test_shared_parent_atomic_admission_pg.py。
新增fixed 4参stage_shared_parent_initial_window_obligation(plan, initialMaterialHash, xid,pid)，无caller Source/窗口/时间/计数JSON。锁本caller原initial_call_authority/initial_obligation材料，派生Source packet/ref→原GUARD实际账户version UPDATE强度→READ_INITIAL_CALL原Suite/Input/Source/父预算/四证书等锁后完整重核。READ_INITIAL_CALL内部返回经原终段核一致性证明的originalFacts供同Owner窗口消费者，不输出raw、不开runtime权；这是本Task未部署artifact兼容追加返回字段，原14与旧七拒绝体不改。
窗口事实仅取原native事实target.tokenLimit，模式仅inflight_upper_bound/fixed_window_rate、unit token、正maxTokens；fixed模式要求原windowSeconds 1..86400和带时区windowAnchor，窗口序号由DBclock-anchor精确floor，时间不接受caller输入。未知未结算占用持续计入所有后续窗口；不靠Source/JWT/TTL或换revision释放，不凭snapshot宣称真正消费。
canonical计数来源 union: 原prepared_parent_debit逐条 + 新initial_target_obligation逐条，按同physicalAccount/tenant锁保护，包含当前本plan一次；不再把window记录另计一次。新核算记录count/token total为native读取快照，先扣当前候选一行及其token，再调用同原_physical_call_capacity_guard_sql('target')，不复制容量判断、不double count。持续持有account写锁直到事务终止；从declared原Source guard获得account version。无需未知history正向fake行；正式旧pool/history映射仍独立缺口。
private initial_window_obligation表plan PK FK initial obligation，native material hash/caller/account绑定、body/hash、FORCE RLS与closed runtime/Provider权限；BEFORE核native caller、同plan材料/obligation和derived账本绑定，UPDATE/DELETE/TRUNCATE拒绝，deferred仍依赖原完整physical ending，无单独COMMIT/Receipt/执行权。窗口记录是终门必要材料而非完整状态机；confirmed charge/settlement/no-effect释放和真正跨窗口transition仍须原正式不可变Receipt及完整终门后续验证。
RED artifact缺失→native metadata/Owner/ACL/两模式字段/early admin deny/rollback、原9artifact仅READ_INITIAL返回追加字段有意变化→fresh真正Source/审批/签名、guard version/natives union正向与bad material/私表/canary/实际COMMIT缺end拒绝/独立全部零。fixture把单独read_initial调用换为本stage内部read（同一真实核，不叠加已验收的额外重核），全Source/期限保留。固定window签名正向若fixture仅inflight如实标缺，不把metadata或手造Source当正向。

1732方案细化：无需扩展READ_INITIAL返回字段，现有9组保持逐字不变。新BEFORE使用同原SOURCE_FACT直接从native材料重读原签名Source，获得真实tokenLimit，核原GUARD同xid的账户version。BEFORE由数据库生成完整body/hash、clock/windowId和native总量，不接受或信任提交body/hash；table INSERT仅传plan/material hash/caller，触发器从原权威字段派生。Stage先GUARD→READ_INITIAL完整call核→INSERT RETURNING触发器生成的snapshot。该snapshot只prepared_window_only，不表示当前时刻可派发；replay返回同一不可变snapshot并仍重核原call，旧/新计数由最终终门重新核对，不能用历史snapshot授权。

1732真实fresh r1：窗口Stage17.22s正向，四真签名/原始Input篡改与坏hash/私表拒绝/实际COMMIT缺完整终门拒绝，独立caller aborted、窗口/材料/两Intent/父hold全零。327相邻通过；原9artifact字节未改。外层Source当前性及supplier cleanup RED保留。仅inflight组件通过，fixed签名正向、非空旧池union/unknown、settlement与跨窗口释放、完整结束和自然首链未通过。下一首选fixed签名Source可达性调查，次选非空旧占用union原生负门；不伪造history、不修改旧TTL。

## 1733 固定窗口原签名正向验收（夹具编码前）
仅新增本Task evidence/fixed-window-native-1733-r1。原source_inputs生成有效account/allocation后，通过原CandidateStore创建新fixed Basis，以新exact ref构造待审批Source，后续Source proposal/approve/native signer原路径全部复用；在签名前选择policy允许fixed。不改既存批准行、不伪造哈希、不延长TTL。当前产品10artifact精确冻结。Stage窗口后验证真实tokenLimit/DB clock生成floor/windowAnchor/windowSeconds、unknown不随窗口释放、全部原重核、3negative/COMMIT缺end拒绝/独立原事务aborted全零。外层旧DEBIT故意inflight-only，若本轮触达该拒绝或原Source期限失败，保留为整轮RED。该验收不证明真正跨窗口settlement。

1733 fixed fresh r1实际正向：aos_test_8eae415b6f96_ti4_test，Stage16.60s，原fixed签名Source/60秒anchor/native DBclock floor/windowIndex独立复核，4签名/3负门/actual COMMIT拒绝/caller aborted/材料窗口父hold全零。外层旧DEBIT原CAPACITY_PHYSICAL_TOKEN_MODE_REQUIRED拒绝，supplier cleanup期限RED均保留。产品文件精确未改，复用上一327相邻证据；fixed身份组件PASS不含settlement/跨窗口释放/完整admission。下一候选一完整terminal node/Receipt/guard核绑定及物理未解除池，候选二非空旧新union overload负门；先调查原完整结束合同再编码，不把旧prepared当已完整承诺的unknown。

## 1734 非空旧/新准备占用合计实际验收（夹具编码前）
精确文件仅本Task evidence/legacy-union-native-1734-r1；产品两文件与原14/10新artifact冻结。候选一完整终门依赖全native node/Receipt/event/RI/window/history，候选二非空物理union（当前批准隔离Task）。选择二：在fresh原Source/两审批四签名caller内，从原prepare_capacity_parent_debit入口用真实target parent/request/ref生成一条prepared_only旧debit，费用1且小于真实父上界，原所有FK/预算/Source核不改。随后原new INITIAL_OBLIGATION与WINDOW应count2、token=原旧debit tokenUnits+新first tokenUpperBound。不把此旧row视为历史unknown，不增加finalizer/execute许可；完整terminal仍缺失，actual COMMIT必拒绝。保存原debit body/hash+新snapshot、独立原函数body/hash/Owner/ACL/caller aborted全零，原外层Source/期限不变。真实negative/whole RED保留；未改产品复用327 hash一致回归。

1734 union r1新窗口返回/requests2后夹具KeyError immutable，原旧入口只返回physicalTokens/native contentHash，没有body。不宣称PASS。独立8表全零、occupation NOLOGIN/7特权false/membership0，终态已知。r2全新Source/审批/签名与库，按原返回physicalRequests1/physicalTokens及native contentHash核合计，不凭Python杜撰immutable；同原产品body/TTL不改。

1734 union r2正向：aos_test_e9920acbd5fd_ti4_test，原旧debit请求1/token10000，新initial10000，window请求2/token20000；4签名/3negative/COMMIT拒绝及独立caller aborted/全部材料和旧debit零/role恢复。外层Source及supplier cleanup期限RED保留，未通过整轮。原DEBIT native在调用前安装hash由原测试核验，清理后函数已撤：不宣称当前body还安装。61 catalog triggers包括RI，不等同actual deferred queue，也不等同完整event fixedpoint。完整terminal及真正history unknown映射仍未验收。产品无变更，327相邻文件hash精确一致。下一先完整终门typed node、Receipt、最后决策及后续RI/事件闭包方案，再RED/最小完整实现，不能加空终门仅为提交。

## 1735 后续旧写者超占实际RED（夹具编码前）
候选一完整终门风险账本/fixedpoint，候选二旧写者兼容顺序矩阵；后者提供前者真正RED。仅本Task evidence/late-legacy-writer-native-1735-r1新增夹具，产品未改。fresh Source/独立审批/原两hold四签名先旧debit1→new initial/window(count2/token20000)→同原旧入口第二debit。旧算法若只认legacy count，应仍accept旧count2/token20000，实际union旧2+new1=3/token30000大于原Source限制2/20000。增加test-owned只读native union窄门在同caller读取实际两账本，同scope/physicalAccount；不接正式入口、不改旧算法、不手写旧row。保存实际RED、原window snapshot非当前事实、COMMIT仍拒绝/aborted/零残留。该结果要求完整终门在最后决策前锁账户并重核native union，不能凭immutable旧snapshot授准入。若Source先到期则真实RED保留，不能当超占正向。

1735 late-writer r1在window内部完整original fact重核遇Source期限，尚未发起第二旧写者；独立8表零/role恢复，不宣称超占。r2全fresh，移除夹具中上一1730/1734已验收的单独retained read（约8.2s）；保留stage/read内部全部原核/签名/TTL与外层旧Source试验，cp retained_readback=None，独立验证不冒称重复read正向。只减少夹具重复工作，不改产品安全检查；再次失败登记真实边界不堆叠重试。

1735 late-writer r2真实RED：aos_test_96285febcfcb_ti4_test，新window旧1+新1=2/token20000后，原旧DEBIT第二次成功，其native totals旧2/token20000、parent allocated2<cap10；test-owned只读native union实际3/token30000，超过原签名2/20000。原actual COMMIT拒绝，独立xid aborted/全部新material与legacy零/role恢复。原快照不是实时准入且full ending仍缺失；不当已部署突破，不改变原旧体。下一文件级最小实现候选为固定live-physical-facts结束窄门：plan/native材料hash/xid/pid，原账户实际UPDATE锁、原Source当前事实、旧新实时union复用原capacity核，保留原9组body并记录有意新artifact；完整end须强制消费该核及所有7native节点/完整risk/Receipt/event/RI，并最终DBclock，不凭该窄门完成full ending。所有等待后重核、late旧写者/顺序/overload必须实际拒绝。完整Task仍active无Delivery，原预算/Root/unknown正式切换不可略去。

## 1736 实时物理合计固定窄门（编码前）
精确产品文件：services/aos-api/aos_api/aip_shared_parent_atomic_admission.py 与 services/aos-api/tests/aip/test_shared_parent_atomic_admission_pg.py。保留现有10组artifact逐字、原14算法/七拒绝体、既存window历史snapshot与TTL。新增READ_LIVE_PHYSICAL四参plan/windowHash/xid/pid，仅physical Owner SECdef/pg_catalog，PUBLIC/runtime/provider无权限，原8上下文先于读表。锁已有window/material/obligation，核native caller/hash/canonical body/raw SHA/physical account绑定。由材料原raw/exact sourceRef调用原GUARD实际账户version UPDATE，取得写锁后调用原SOURCE_FACT完整Source核（不信window内旧limit），账户/版本/xmin核实际同caller。按同account原prepared_parent_debit+newinitial_target_obligation实时union；本plan已计入一次，扣自身后复用原capacity核。先前snapshot不能授权当前合计，超占实际CAPACITY_PHYSICAL_CAPACITY_EXCEEDED拒绝。返回current facts/counter/sourceLimits/DBclock和hash，executionAllowed=false，不写新表/Receipt/Intent，不开启完整终门；全Suite/Input/4cert/Root/预算/RI/最后决策必须完整终门另外强制消费，禁止以该子核代替all-node ending。
RED：上一真实late writer3/30000超限2/20000+新artifact缺失。GREEN：native DDL/Owner/ACL/context拒绝/rollback21结构，加10beforeimage精确；fresh原审批Source4签名/native window后先新窄门正向2/20000，再原旧DEBIT后新窄门拒绝3/30000（原TTL和旧体不改），actual COMMIT缺end拒绝/独立全零/role恢复。若期限先拒绝，保留真实RED，不宣称新核实际overload验收。

1736 live r1未到新窄门即window原Source期限RED；不宣称新核native正向或late拒绝。新核原生body/Owner/closed ACL已独立核、8表零、role恢复。328相邻及原10byte image通过只属WIP结构，whole admission未通过。下一先整条原准备链时序与重复原核调查，保留生产全部原权限/签名/期限，不用窄化夹具代替whole pipeline验收。

## 1738 保存点真实行版本归属 RED 与最小修复
函数级真实观测得到original fact boundary1848次/self47.543秒，仍不删原审核或延长期限。r1首live成功；真实第二legacy写入后，SAVEPOINT中的live先误拒SHARED_ADMISSION_LIVE_PHYSICAL_GUARD_REQUIRED，未证容量门。独立原生临时表探针确认pg_current_xact_id仍顶层而UPDATE行xmin为子事务；原试验8表零行及临时参数ACL恢复。

精确产品文件仅services/aos-api/aos_api/aip_shared_parent_atomic_admission.py的READ_LIVE_PHYSICAL新构件。删除把xmin误当顶层xid的筛选，保留原GUARD实际version UPDATE并持有account写锁、后等待原SOURCE_FACT完整核验；随后固定账户tenant FOR UPDATE回读版本，显式要求实际server原GUARD返回xid/pid等于当前绑定的p_xid/p_pid、physicalAccountId精确、version精确。guard_doc只能来自刚执行的固定原函数，不来自调用方；完整终结仍需独立冻结原函数/Owner/权限。版本返回值及独占更新锁证明本调用的写入，不以pg_xact_status任意inprogress行代替，不缓存Source或借别事务版本。其他10artifacts和旧14生成器字节不变。

RED是r1全原链真实错误与临时子事务差异；GREEN必须新Source/新独立审批/真SCRAM同caller的首次live回读2/20000、实际第二旧debit后的保存点live精确CAPACITY_PHYSICAL_CAPACITY_EXCEEDED、真实COMMIT拒绝与独立回滚0行/角色/参数ACL恢复；原链剩余Source邻接与供应方清理如期限RED仍记录whole失败。再串行328相邻/metadata测试及方案一致性复审，不增正式授予、不触真实库、不声称完整准入或发布完成。

## 1739 完整原父风险账本：新路径固定回读与旧对切换拒绝
本轮沿原第3/11.3完整目标，不以单个helper交付整Task。现有Target/Judge已UNIQUE(org,project,request,case,attempt)，不再误称只有plan唯一；Issuer pending有全originalRisk而physical新路径无完整risk记录。精确产品文件仍为aip_shared_parent_atomic_admission.py、tests/aip/test_shared_parent_atomic_admission_pg.py；证据本目录。新增显式artifact generator不安装真库、不更改原11artifact/旧14函数与七无条件拒绝门。

新增physical private complete_parent_risk：plan PK、正向tenant、原target/judge request对UNIQUE、两原hold/account/caller xidpid、pending/authority hash、包含全originalRisk/body/hash，不额外reserve或allocate任何费用。原held父cap仍唯一金额权威；风险没有TTL或自动release语义。当前完整终结门尚缺失，新记录复用当前deferred完整结束拒绝。

固定4参数stage(plan,pendingHash,xid,pid)仅physical Owner闭EXECUTE；调用原READ_RETAINED（原Source/两个Owner/Root/四签名/全manifest和caller验证），不接受可信bodyJSON。查原prepared_plan_risk同tenant请求对FOR SHARE；任何已存在旧对明确LEGACY_RISK_PAIR_REQUIRES_CUTOVER拒绝，不假升级prepared旧行、不改旧状态。派生固定新body与hash，INSERT ON CONFLICT DO NOTHING、同plan/body/列/caller精确回读，另plan抢同对拒绝；所有可能等锁和唯一冲突之后再次完整READ_RETAINED且等于初次，避免缓存当前授权。BEFORE INSERT绑定完整risk/hash/tenant/hold/request/account/caller与新body，不开放Issuer schema/table权限。UPDATE/DELETE/TRUNCATE不可变、FORCE RLS；所有公开/运行/issuer无EXECUTE，无提交权限。

RED先新artifact缺失；GREEN原生DDL/Owner/ACL/RLS/请求对唯一/完整guard/恶意caller及实际DDL回滚。真实原链另新Source/独立审批/真SCRAM正向stage含全cases/4legs/两父cap，与原risk/hash精确；新记录为awaiting_full_admission，不是已准入/dispatch。旧native队列、RI、完整Receipt/end-channel/真实准入COMMIT仍待实现；整链Source期限RED如实保留，不延时、改签名或断言fullTask通过。下一完整结束步骤需将risk与全部实际native effect及事件共同冻结、等锁后全权威/时钟复核，不能只回读此表就允许提交。

### 1739 risk native r1 boundary diagnosis and r2 harness repair
Readonly reconciliation proves r1 terminated before risk stage. The added risk wrapper reused local `sig`, so the later initial-intents Owner/ACL setup applied to the wrong test function. Retained fresh DB exposes test_owned_initial_intents as aos_app-owned with default PUBLIC execute; original epoch-pair boundary correctly rejected it. Repair only fresh r2 harness by explicitly rebinding INITIAL_INTENT before exact Owner/REVOKE/GRANT. Preserve r1, all production boundaries and Source validity; use a newly generated original transaction, not replay. Root and full ending remain unaccepted.

### 1740 next registered candidate: actual event/RI end inventory
Candidate1: full native admission end event/RI and immutable Receipt, already authorized isolated implementation; depends on exact current nodes, original deferred seven denial gates, fixed C/root source and legacy cutover. Candidate2: original Source whole setup/catalog timing, registered but needs exact original fixture/dependency scope; cannot change Source TTL or reduce fences. Choose1 now: new event-ri-inventory-1740.py/json in this evidence directory only. SERIALIZABLE READ ONLY against exact retained risk-r2 lab database; record pg_trigger and FK constraints/function body hashes, absent END_CHANNEL/PHYSICAL_END/Receipt, all8 tables and current native rows. This inventory is not an event queue fixedpoint proof, does not run SET CONSTRAINTS or write, and cannot certify complete COMMIT. Use findings for the full end plan before product coding.

1740 native inventory result: exact retained r2 has94 triggers/103constraints,11 deferred user triggers (8 new shared-parent endings +3 installed legacy preparations),14 immediate FKs and no deferred FK among these namespaces. Both complete ending functions absent. Eight shared tables empty after risk r2 rollback. This partial namespace inventory does not claim original seven guards all deployed, global queue drained, fixedpoint, final Receipt, or COMMIT pass. Next full ending must validate exact current graph and authorized native verifier/source metadata, register actual end event semantics and preserve every existing RI action; do not substitute catalog presence for pending event closure.
