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
