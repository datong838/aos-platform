# typed Model隔离证明实施包

基线m1 8658a3fcb75d280eb454bc342629af8a9fb72c80/AOS-001513。用户已批准Model评测设计/隔离实现；沿父joint/model-proof-implementation-contract、model-journal-owner-contract与report/signature前置调查。此包整体持续实施，不把合同DTO/单测/迁移空表当完整退出。正式执行/质量/Route仍依各自门。

## 文件级范围

新增 services/aos-api/aos_api/aip_model_eval_execution_contracts.py、aip_model_eval_execution_authority.py、aip_model_eval_execution_reader.py；新增 alembic/versions/a0v_158_model_eval_execution_authority.py（当前最新157，无158）；新增 tests/aip/test_model_eval_execution_contracts.py、test_model_eval_execution_authority_pg.py；证据 .evidence/gt-model-typed-proof-20261008。现旧Skill/Model拒绝门、原预算内核、旧迁移均不修改；若后续joint接线需要原文件，另精确登记归属，无跨Lease施工。

## 一体合同

strict typed manifest绑定tenant、原approved Model request/ref/hash、原proposal/approval、suite/contract/data/case输入集合、精确Target与独立Judge、每腿自己的Source/physical/price/quota/budget/Intent与attempt。先输入manifest hash，后实际执行回执/Usage/费用义务与原Report hash关联，消除循环签名。Target/Judge identity/key/Intent不得复用；deterministic Judge明确无Provider而不是伪零Usage。未知结果不得新attempt重发。Route没有原申请，当前包拒绝Route。

独立NOLOGIN private Owner、显式撤default/PUBLIC/runtime直接写权；不可变manifest/case-result/义务事件/report关联，专用issuer/签名域/撤回，原caller实际COMMIT和原审批/Source/budget/joint事实需精确窄桥。未具备原joint/真实身份的正向仅隔离测试，不设置runtime执行开关。证明reader同snapshot核原request审批、issuer当前性、全部case/result/Usage/Intent及report关联；旧Skill域保持。

## RED→退出

先确认已批准原Model申请可以正常解析，再用真正该申请构造新manifest，缺实现应RED；拒绝原request hash不一致、跨租户、Judge借Target费用/Intent、缺case/未知重发。接下来完整合同实现与private Owner/native已知COMMIT、rollback/replay、直接SQL负门、错误签名/费用/来源/撤回/当前性，旧Skill/Logic/预算相邻累计。父joint原生桥未齐时不启用执行、不虚构输入；包保持ACTIVE直到全包真实证据齐，不造Delivery/Goal complete。当前API不部署，正式库只读，禁Host/worker/Provider/商城/旧Run/手工定义。

## 首段字段合同细化（AOS-001514，编码前）

首段仅Model-backed Judge（deterministic另需精确类型与Owner证明，不默认无费用）。每case独立target/judge腿：tenant、purpose、current Model/Provider/Price/Quota/Budget refs、signed Source/physicalAccount候选ref、approval/hold/jointReceipt/Intent exact refs、identity/key hash、attempt固定1。Target腿精确匹配原申请source/provider/price/quota/budget；Judge费用审批/hold不得借Target，同物理account或同预算policy可以合法共享，不能误禁。所有腿Intent/hold全局唯一，每case身份/key分离；每个case含input/expected hash，case集合摘要由原canonical_hash计算并拒绝重复caseId。manifest绑定原Request及canonical hash、tenant与明确schema，executionAllowed固定false，不能作为签发/准入票据。新joint ref只是描述所需事实，不表示已存在/可信。输入DTO strict拒额外字段；强制重新解析嵌入原Request防model_copy绕过原合法形状。当前没有Report输出，避免循环hash。合法来源当前性、授权、实际持有和签名统一留独立Owner/reader核实。

复审新增RED：Pydantic Literal会将True视作1、0视作False，三个控制字段实测未拒绝。schemaVersion/attempt必须原生int（禁止bool）且精确1，executionAllowed必须原生bool且精确False；添加before field validator，不能以类型注解推定严守。仅新合同内最小修复，旧合同不修改。

## 接续复审：typed实例复制不能免检（AOS-001515）

候选一新Model包Owner/持久reader；候选二ordinary/Eval自然竞争仍待来源。先验证新包当前dirty合同的输入免检风险：Pydantic已解析实例及model_copy/model_construct可能绕过字段validator；新增typed复制控制字段/深层ref hash与id/attempt/key的真实负测试，若RED仅本合同新增规范化输入和重新解析（不改全局AipContractModel/旧Skill）。完整typed包仍须Owner/native，不把此自复审当所有签发验证通过。范围仍两个已登记产品文件与本证据目录；正式库无效果。

## 原生持久边界首段（AOS-001516，编码前）
候选一：本Task Model private Owner与持久证明；已授权隔离实现，依赖原joint/签名桥，首段不得开放写入口。候选二：普通经营/Eval自然竞争；已登记，但原ordinary binding与审批Source缺失，不能用mock补正向。本轮选择候选一。

新增目录精确为 services/aos-api/aos_api/aip_model_eval_execution_authority.py、services/aos-api/alembic/versions/a0v_158_model_eval_execution_authority.py、services/aos-api/tests/aip/test_model_eval_execution_authority_pg.py。Owner aos_model_eval_execution_owner、schema aos_model_eval_execution_private；独立NOLOGIN/NOINHERIT/无高权限/无membership，已有保留角色有漂移则拒绝，不修补未知历史。角色检查复用既有安全原则，不能复用capacity身份。四张不可变表 manifest、case_result、obligation_event、report_link；各记录仅保存逐字节body和其sha256，tenant固定正向，FK以tenant+execution绑定manifest，结果与义务进一步绑定case/purpose/attempt。manifest执行ID唯一、输入hash不可更换；case_result每case/purpose/attempt唯一；report_link每execution唯一，明确后置Report association。body中的签名/原授权/currentness留专用reader和窄桥，不以body可存储当合法证明。

本阶段没有issuer、LOGIN、role membership、PUBLIC/runtime schema权限、函数调用写入口、信任根、默认数据或执行开关。新schema显式撤创建者和Owner在该schema的table/sequence/function默认PUBLIC/runtime权限，再逐对象撤权；不修改public已有默认ACL或旧表。所有表独立Owner、FORCE RLS且仅Owner双tenant策略；UPDATE/DELETE/TRUNCATE不可变trigger，函数固定pg_catalog。原生测试先在新全schema157库验证缺实现RED，再完整158隔离迁移，核角色/ownership/defaultACL/空表和runtime实际SQL42501；角色插入测试仅管理员SET LOCAL Owner+正确scope，SAVEPOINT测试后整个事务ROLLBACK，不制造签名通过或业务COMMIT。后续完整可信正向COMMIT、重放/撤回、费用结算/Usage/Report-reader仍pending，Task不Delivery、不提交空表包，不迁移当前正式库。

首段复审澄清：obligation_event的case/purpose/attempt是归属字段，当前FK仅绑定manifest，尚未核原批准case集合/Intent/Usage合法性；这些语义需窄桥与reader，不能据表约束宣称执行证明。PostgreSQL schema级函数默认REVOKE不能取消创建者全局PUBLIC隐式EXECUTE，因此所有本次实际函数必须逐对象REVOKE；仅新Owner的全局函数默认明确撤PUBLIC，测试验证Owner未来对象权限。不会修改aos_app全局默认ACL；后续管理员新增函数须显式撤权和审计。原始RED与green-r1曾因dict_row误用KeyError，非缺实现证明；red-r2在保留全157库真正断言缺namespace。green-r2的TRUNCATE被原FK先拒绝(0A000)，改用明确CASCADE以实际触发不可变42501，不接受错误门当目标门。r3验证全部ROLLBACK，无drop/未知重试。

## 持久计划读取校验（AOS-001517，产品编码前）

候选一为已授权的本 Task 完整 Model 证明 reader；候选二为已登记 ordinary/Eval 自然竞争，后者仍缺原生 ordinary 申请前置。本轮选候选一的读取前置，不构造 mock 权限。先前补方案的 shell 输入编码失败，没有写入；测试先行 RED，现补齐方案再写产品代码。

精确新增 services/aos-api/aos_api/aip_model_eval_execution_reader.py，修改已登记 tests/aip/test_model_eval_execution_authority_pg.py。read_model_execution_plan 仅读描述计划，不返回 Verified 对象，不替代签名与当前授权验证。参数为 expected_tenant、execution_id、manifest_hash；双租户固定正向，执行 ID 非空且 trim，hash 为 64 位小写 hex。必须同 conn 实际独立 Owner、精确 scope GUC、REPEATABLE READ 或 SERIALIZABLE；不新建连接、不改角色、不写入、不新增 GRANT 或公开入口。

同快照 SELECT 精确 tenant/id：原始 body sha256=stored hash=expected hash；新 strict Manifest 解析后 tenant/id 一致，原 canonical_hash(parsed JSON)=原始 body hash，拒重复 key、非规范 body、额外字段和内容重绑。返回 executionAllowed=false；历史 request 过期不影响描述解析，不能据此当当前权限。Target leg 的 model_ref 是当前 source 治理，而原 request.target_ref 是待评测下一版本的语义 hash；后继真实 case 签名必须独立绑定候选 target_ref。

原生 RED 为完整158隔离库缺 reader 模块。GREEN 使用管理员 SET LOCAL Owner 插入纯合成 typed plan，同事务读取；运行角色、管理员角色、错 scope/hash/id、READ COMMITTED、错误 typed body 和重复 key 均拒绝。全外层 ROLLBACK，独立回读零残留。完整 issuer/审批/joint/Usage/撤回/currentness/report proof 尚待，任务不 Delivery、旧拒绝门不解除、当前库和 Goal 状态不改。

快照复审新增真实 RED：autocommit=True 且 session default SERIALIZABLE、Owner/正确 scope 时，旧读取实现直到缺记录才拒绝，没在入口拒绝缺调用者事务。需在任何 query 前检查 psycopg TransactionStatus.INTRANS；没有现成事务直接拒绝，不自己 BEGIN 或补 scope。显式 BEGIN 的 autocommit 连接仍可用，因为实际 INTRANS 才是条件。测试匹配入口拒绝原因，不能以最终 missing-record 遮蔽未守住快照。

## 逐case证明前的精确标识一致性（产品编码前）

本轮原卷重启Task已Delivery，m1证据提交e7bb9bac，authority001519；仍沿本Task原Owner/Lease。已登记候选：Model逐case证明协议（已授权隔离实现，尚需独立issuer/current roots/原joint与真实Usage）；ordinary/Eval自然竞争（已登记，缺原生ordinary申请精确Intent/审批前置）。先选Model描述输入的一项安全独立修复：源码调查发现executionId/requestId/caseId只限制长度，允许纯空白或首尾空白，而持久reader与存储executionId要求trim精确。它们是签名、case集合和后继Report关联键，不能在后继消费时隐式归一化。

精确修改services/aos-api/aos_api/aip_model_eval_execution_contracts.py及tests/aip/test_model_eval_execution_contracts.py。在原描述合同校验层拒绝空白/首尾空白executionId、requestId、caseId，不自动strip，不改原Request、hash算法、引用类型或旧Skill域。测试对case变体重新计算原case_set_hash，证明拒绝来自标识规则而非hash失配；同时保留合法原标识和model_copy强制重解析边界。先真实RED后最小validator/GREEN及相邻既有合同/读取测试；不修改当前库，不签发身份/证明，不开runtime，不把此小修复当整个Model Task完成。

## Model逐case签名输入绑定（AOS-001520，编码前）

范围保持上述合同与纯测试及证据；不增加角色、迁移、信任根或签发入口。新增ModelEvalCaseSigningInput严格描述签名前输入，schema aos.model-eval-case-signing-input/v1，tenant/executionId/manifestHash/requestHash/caseId/purpose/candidateRef/leg/inputHash/outputHash/occurredAt；candidateRef精确等于原Request.target_ref，leg精确等于该case对应原计划leg，分别绑定候选与当前source治理。Target不含Judge结论字段；Judge必须targetClaimHash/actualHash/passed/detailCode，expectedHash来自原case（允许原case无expected）；passed原生bool、时间须有时区并规范到UTC。

canonical_model_case_signing_bytes为纯校验与规范签名输入，不返回Verified、不给执行许可。每次重新解析原manifest与claim以防model_copy绕过；manifestHash使用原canonical_hash，requestHash/tenant/id/case/leg均逐项相等。调用者须提供实际input/output bytes，SHA256与claim精确匹配。Target输入绑定case输入；Judge接收完整Target claim，重新绑定其计划/候选/purpose、原case expectedHash、actualHash=Target.outputHash，targetClaimHash=新Model域下Target完整输入摘要，且Target时间不晚于Judge。Judge输入为调用者原字节hash，不推断raw结果语义或虚构Usage。

签名domain专用AOS-MODEL-EVAL-CASE-SIGNING-INPUT-v1，JSON沿现有规范sort_keys/ensure_ascii=False/separators/allow_nan=False。不触碰旧Skill v1 domain。测试先缺实现RED，合法Target→Judge输入纯字节关联及原manifest/候选/leg/input/output/expected/purpose/target摘要/时序/typedcopy负门；合成case引用明确仍非合法权限。此步骤只准备签名原文；真实签名、证书/撤回/currentness、原joint/Usage费用义务和Report解析仍pending。不给persisted plan升级为可信证明，不以本段GREEN做整体Delivery。

## AOS-001532 Usage来源实证纠偏

见 usage-source-findings.md 与 usage-source-investigation.json：原Model hold为申请/批准唯一的parent hold，而现描述manifest全case hold唯一不可落地多case。先冻结parent hold与逐调用allocation/Intent原子协议，再替换hold唯一为allocation唯一并证明金额上界；不能只删除唯一检查。Usage本表无Model case/Intent字段，原content operation/通用token sourceHash不能借用。完整费用/Report接线先依真实transport原文及原权威窄桥，仍不授执行。

## AOS-001533 parent/allocation纠偏实现检查点

见 parent-allocation-plan.md/checkpoint.md：描述manifest以申请级parent hold对应原request/审批，允许多case共享；增加每次必需allocation ref/金额/唯一Intent和总额上限。163pure相邻/8native及35持久隔离样本只读通过；实际allocation原子账本、原hold权威窄桥和费用/Usage/Report仍下一，DTO非预算已分配，Task未Delivery。

## 2026-10-10/AOS-001701重启后完整原生复审

候选一：原Model158完整持久/issuer/identity/reader相邻原生集合，已授权隔离实现，完整joint/费用/Report依赖尚待；候选二：Judge159原budget三桶/parent，全Source/physical/Intent finalizer依赖尚待。先选一。当前m1 b3590e8b9、原库157、原Task原owner已合法续租，无并行写者，不从维护Task跨域修改。

检查发现纯证书夹具固定2026-10-08→09，原生读回使用数据库clock_timestamp，今天真实窗口已过期。先新建本Task runner reboot-native-review.py，仅核固定Desktop lab.json的container/volume/cluster5441、原私有admin passfile，通过原conftest新UUID库/全部迁移初始化，AOS_TEST_RETAIN_DATABASE=1保留库；原库18435禁连接。每次独立attempt/terminal、新库新journal，不重放旧COMMIT。第一轮按全部原Model native集合执行、--maxfail=1，定位失败。初始零对象断言应在第一次COMMIT前执行，保留集合全部节点不删失败测试。

确认日期失败后才修改本Task精确文件 services/aos-api/tests/aip/test_model_eval_execution_contracts.py、test_model_eval_execution_authority_pg.py：pure helper默认固定日期以保留其确定性断言；增加显式夹具时间参数，只在native test从同目标数据库READ ONLY clock_timestamp取当前时间，生成并真实重签root/cert/case原文，不替换/模拟生产时钟、不绕过当前性。正向证书保留明确短期限，原半开区间/withdrawal/锁等待反例继续用数据库时钟真实等待。生产module/迁移不因测试过期修改。专项RED→全部native与纯合同累计、原生独立读回及精确hash复审后才判断158源可提交；完整Task无Delivery、当前159维护门不提前放行。

r1完整收集34节点，前两门PASS，持久证书因实际半开区间过期RED；r2日期修复后该节点PASS及两epoch竞争PASS，但描述reader因前一节点已COMMIT同test-plan主键RED。原native测试此前分别fresh fixture运行，部分还要求全库零/直接首次install，不适合共享一个库。不得删除已持久证据或放松零状态断言。新增reboot-native-collection.py，冻结r1完整34node集合与源码hash，逐节点独立原conftest fresh库、同已核Desktop隔离cluster、独立attempt/terminal保留库。串行子进程，每节点目标全相同原用例，不绕过任何节点；失败停下诊断，旧节点不原库重放，新修复仅在新fixture验证。完整通过须34/34且全部独立终态、本次sourcehash一致，原34次fresh迁移安装亦单独记为隔离证据，不证明提交图159、当前库迁移或完整Source/joint执行。

容量接续对账：实际resource-launch-stop保存的child为n21/PID18502；初始硬编码18的观察文件数量不准确，仅作历史失败诊断。重新逐个handle/terminal核实n01..n21全21PASS且无活跃子进程，parent终态143由本轮主动终止；n22从未启动。不得按前文18作重跑入口。

本Task已授权隔离原生验证，新增本目录reboot-native-lab.py及reboot-lab.json，独立新容器aos-model-native-shm-20261010与同名-data命名卷、5442、原完全相同C镜像bcdf34e...、shm1GiB/memory2GiB无swap/单CPU；保留旧5441全部21库，禁止delete/drop/清统计/重启旧资源。新随机admin SCRAM仅新私有0600passfile/密码文件，不输出口令，data卷显式nocopy，根只chown完全空新卷。每步独立intent与终态，失败只读对账不重复创建。两引擎原容器ID/启动/挂载/端口逐项前后不变。新增runner仅可选择本目录正式回读的reboot-lab.json；独立r4续完整原34集合未执行的n22..n34，核21个原已知PASS/精确产品hash一致，不能重放任何已有DB操作。新runner/harness变化分别hash绑定，不伪称同制品。扩容只解除已证容量约束，不声称修复PG崩溃根因。

新lab创建已知终态：容器64350ecc...已运行、fsync/synchronous_commit=on；宿主资源复核因七个旧容器Mounts数组顺序变化失败。只读逐字段诊断证明唯数组顺序不同，完整mount多重集、ID/启动时间/端口全相同；禁止重跑创建器。新增reboot_resource_review.py/test_reboot_resource_review.py，只对mount列表排序且保留重复与所有字段；RW/Source/卷/目标/启动/端口变化必拒绝。RED先验证旧直接列表比较拒绝换序，再新核对器6项反例；新增reconcile-reboot-lab.py仅核固定已创建ID/卷/镜像/限额/端口/cluster/耐久和全部旧资源，读取既有私有passfile，不创建或更改任何资源。复核通过才写lab receipt及接续剩余13节点。

34节点接续结束后的独立读回：新增本Task目录reboot-native-audit.py，仅消费r4完整终态和每child attempt/terminal，核原34集合、六精确源hash、两个固定隔离cluster以及34个不同保留库。逐库READ ONLY读取alembic_version、数据库名、pg_control_system和耐久参数，读回159只作隔离图证据。比对扩容前全部旧容器ID/启动/挂载/端口；正式卷仅Docker元数据读回，不连接或写入。报告明确root信任、正式迁移、业务首链及完整Task均未通过，不签Delivery。

r4 n22..28七PASS；n29真实RED：global withdrawal内部i==2错误密钥夹具仍_certificate_input()默认旧日期，根已用新窗口故被生产半开区间提前拒绝。仅该调用追加**interval，不改变错误密钥/用途反例或生产当前性。失败数据库保留、事务终态已知。新r5-n29 fresh单节点验证，再r6完整34集合重新验证修改后精确hash；旧28PASS保留为旧hash历史，不冒充新hash累计。独立audit将消费r6全部结果。

部署复审：reboot-publication-dependency-audit.json冻结13个Model/Judge相关模块，七文件尚不在HEAD；reboot-migration-installation-gap.json证明158 upgrade仅三基础installer。identity/运行executor fact/target fact/origin四组件为测试显式安装，不能把完整native验证等同当前迁移安装已覆盖。后续先原Task3正式续租/源native复审与Task4三桶复审，再精确发布惰性源码图；完整身份/runtime组合部署须单独登记实际迁移包及权限负门，不借空存储Delivery解除运行禁入。当前测试进程冻结源期间不修改产品/迁移、不更新authority导致其失配。
