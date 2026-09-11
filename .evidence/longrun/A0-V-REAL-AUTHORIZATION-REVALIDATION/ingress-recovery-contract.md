# 真实接入恢复合同与现状核查

2026-09-11，基线c427a848。目标是提交过的同一批次可以恢复，不是重新从变化的源取一批再称为重试。

## 当前证据

- wave_ext.retry_dlq 仅调用 ec_dlq_store.retry_failure，无执行器调用。
- retry_failure 只更新 retried/retry_count，写 retry receipt 与 retry_succeeded event。不存在源读取、对象提交、任务续跑动作，事件名不能作为恢复成功证据。
- record_failure 保存错误、脱敏metadata与hash，不保存原source/output rows。ec_dlq_handler明确过滤业务payload，不应往该metadata塞业务原文绕过隔离。
- phase5_pipeline_engine 将图与sample_input深拷贝交线程，但这是内存快照；ec_live_executor局部input/output也未形成不可变恢复对象。
- ecom_consistency_store.apply_batch先查exact Receipt再写，具备单批重放基础。当前writer会重新构造命令及读取checkpoint，不能自动等同于保存原命令。
- Dataset/history已同事务，Dataset发布后置；跨OT/派生/投影/Dataset仍不是同一事务。

## 实施路径

1. 新增租户作用域不可变接入批次存储，绑定run_id、pipeline_id、当前管道/源配置版本、规范输出payload及hash、序列化规则、初始exact BatchCommand。仅存执行需要的规范业务行；不得存SSH/DB凭据或整份source配置。原payload仅内部执行Owner可读，普通列表只返回状态/引用。
2. 在任何OT写入前保存批次；唯一键scope/run_id，重复同hash可回读，异hash冲突。缺少run_id或配置版本不允许宣称可恢复。规范化需要的时间戳必须已固定，恢复不再重盖当前时间。
3. 阶段以批次引用关联既有OT/派生Receipt，使用租户与批次锁串行；恢复从保存的同一命令开始核验/重放，禁止重读源替换。OT已成功时验证Receipt；派生按现有CAS检查输入revision；不能猜测成功或覆盖后来变化。
4. 投影用本批确切Outbox/对象revision证明完成；现有project_pending的局部pending不是全量指标，不能作为本批完成门。Dataset成功必须绑定批次与已完成阶段回执。
5. DLQ重试只先记requested，工作器取得批次并完成阶段后才能记succeeded；失败记failed。没有原批次的旧记录必须明确不可自动恢复，另建新运行并标明新源读取，不能伪造旧输入。
6. 故障验证覆盖保存后/OT提交后/派生后/投影后/Dataset提交后崩溃；重启后不再源读、不重复权威副作用、scope canary隔离、hash漂移拒绝。随后才在真实配置恢复后对栖月汇实际数据做同样验证。

## 文件与退出条件

计划涉及 services/aos-api/aos_api/ec_live_executor.py、ec_ot_writer.py、ec_dlq_store.py、新接入批次Owner、Alembic迁移及专项PG测试；先核对当前migration head与既有权限模板，再写DDL。沿用现有失败队列及Receipt，不创建平行审批权威。

退出条件是原输入跨进程恢复证据，而非新表/测试绿。保留单写者、租户隔离、真实数据权限、无凭据输出。不push，230 L0挂起。本文件为核查与施工合同，尚未实现批次Owner/工作器；完整经营首链和八工作台未完成。

## 已准备派生阶段恢复入口（本轮实施）

新增 ec_ingress_recovery.py 内部函数，仅处理原基础命令已提交且原派生命令已保存的运行。复用Journal当前running schedule/source/graph绑定检查，持有调用方事务行锁直至返回；不开放HTTP，不伪造DLQ成功，不做未准备阶段的推断。基础exact Receipt不存在或存在ignored对象/关系时拒绝，必须另行对账。派生命令只反序列化原记录，复用ConsistencyStore幂等与CAS；中途失败不回滚已提交项，下次同命令续跑。

文件：services/aos-api/aos_api/ec_ingress_journal.py 提取可复用绑定检查；同目录新增ec_ingress_recovery.py；tests/test_ec_ingress_recovery.py验证部分提交后重放、缺失/不完整基础回执、绑定拒绝与命令缺失。SQLite验证真实ConsistencyStore写入；Journal/绑定用测试替身，PG绑定另有专项。不得以这些测试声称真实源或完整恢复已通。

仍缺原始辅助输入持久化、恢复claim/worker、当前执行授权、精确输入revision来源、投影完成和Dataset接续；该函数只有内部已授权执行者可以装配。回滚移除新入口及还原提取，不变更现有executor行为或数据。

## 规范恢复输入随基础命令原子保存

2026-09-11，基线b0968513。扩展现有envelope可选outputRows，复用a0v005不可变行及同一INSERT，无新表/DDL。旧envelope仍可读；只有携带outputRows的批次具备恢复派生准备所需输入。保存仅提取OT/Link规范字段及pay_time、_order_create_time、delivery_time辅助字段；不保存任意原始源行、连接配置或凭据。JSON规范化datetime/Decimal，拒绝未知类型与非有限数字。通过原OT规范器重建对象和关系，要求与父BatchCommand逐项一致；固定时间值在保存前已生成，恢复不盖当前时间。

文件：services/aos-api/aos_api/ec_ingress_journal.py（可选字段、规范化、完整性验证），tests/test_ec_ingress_input.py与tests/aip/test_a0v_ingress_journal_pg.py。验证datetime往返、计算辅助字段保留、基础漂移拒绝、幂等冲突及跨连接/跨租户读取。既有派生命令parentHash自然覆盖此字段。

此规范快照用于恢复计算，不保证旧Dataset全部raw列可重建；Dataset完整输出合同另行接续。实际executor暂不切换，精确输入revision及claim仍需实现；该变更不得被称为完整可恢复。

## 原批次派生版本水位

2026-09-11，基线6d4ae1b7。现有get_latest_authoritative_revision按租户全局max读取，恢复时会纳入后续无关写入。新增ConsistencyStore.read_committed_batch_revision：同事务exact核验基础Receipt，拒绝ignored，限定scope/platform/shop/authority_tx_id及authoritative_store非派生事件，核对Outbox数量与Receipt实际写入/删除数量，再返回该批max revision；缺失/残缺拒绝，不借用最新全局值。保留旧接口，不改变现有未切换executor。

ec_ot_writer新增prepare_derived_commands_for_batch，先校验调用scope/pipeline与基础命令，再用规范outputRows及原批水位准备；原prepare/sink保持行为。此水位是本批提交边界，不等同逐个关联聚合输入的完整来源证明；辅助输入已保存但来源版本仍需补齐。实际恢复claim/原子派生准备仍未接入，不能声称完整恢复。

文件：services/aos-api/aos_api/ecom_consistency_store.py、ec_ot_writer.py；tests/test_ecom_consistency_store.py、test_ec_derived_prepare.py。测试无关后续批次不会改变水位、缺失Outbox/缺Receipt/ignored拒绝、exact冲突、规范派生命令使用本批水位。仅通过既有Store写入，测试SQLite；非真实源/PG组合证明。

## 基础与派生权威阶段恢复装配

2026-09-11，基线359e1e54。新增recover_saved_authoritative_stages内部入口，调用方提供既有租户连接工厂（成功退出提交事务）及Store。第一连接：原run事务锁→当前绑定核验→原基础命令Receipt-first apply→核验原批水位→若无派生命令则从保存outputRows准备并保存→退出提交。第二连接：再锁原run/核验当前绑定与原水位→只执行已保存派生命令。无输出快照且未准备的旧批次在基础写入前拒绝；已保存的派生命令不重新准备。派生中断不回滚已提交基础或派生前缀，重试复用原命令。

文件：ec_ingress_journal.py增加scope/run事务锁；ec_ingress_recovery.py装配并核验saved派生水位；test_ec_ingress_recovery.py与tests/aip/test_a0v_ingress_journal_pg.py。验证跨连接保存后执行、重复重放、保存故障不派生、来源漂移拒绝。锁用于本run阶段串行，不替代调度claim/真实授权；仍不接HTTP、不自动标记DLQ/运行成功，投影Dataset阶段未完成。

## 实际投影完成门修正

2026-09-11，基线548fefad。检查实际接线发现project_pending返回len(rows)-projected，事务成功时恒为0，不能代表队列剩余。改为同事务查询本scope真实未投影authoritative_store计数。新增project_until_caught_up按既有500行事务批量处理，使用实际executor monotonic deadline/cancel_event；无可租用行但pending>0时短等待，超时/取消抛固定错误，禁止Dataset成功发布。ec_live_executor改用该入口，不改写Outbox Owner，不双写。

文件：services/aos-api/aos_api/ecom_projector.py、ec_live_executor.py；tests/test_ec_ingress_preflight.py、新test_ec_projection_drain.py、tests/aip/test_a0v_projection_pending_pg.py。真实PG隔离schema验证跨批剩余与租户隔离；模拟时钟验证续批、取消、期限及无效结果；实际executor的阶段顺序专项覆盖Dataset阻断。

这仍是scope队列清空门，不是exact原批逐对象证明；持续其他写入可能导致保守超时，后续恢复需精确批次完成门。另纠正前述Dataset raw全列缺失推断：当前sink_to_dataset只取len(output_rows)写元数据/历史，并不持久化raw行，因此当前恢复Dataset计数无需全部raw列；需解决的是成功记录幂等和阶段对账。

## Dataset前exact权威完成核验

2026-09-11，基线eddd874e。Dataset历史会替换且Build随机ID，不能当持久恢复Receipt。先在ConsistencyStore增加只读派生Receipt核验，复用原receipt_id/hash算法；增加原批完成读取：exact基础Receipt/水位、保存派生对应基础身份且唯一、派生input_revision等于原批水位、每项exact派生Receipt、每个authority_tx_id的Outbox数量与Receipt结果匹配，汇总projected/pending。缺Receipt/事件数量错误拒绝；未投影返回pending，不冒充完成。无重放写入、无全租户最新值替代。

文件：services/aos-api/aos_api/ecom_consistency_store.py和tests/test_ecom_consistency_store.py；测试基础/派生后未投影、逐步投影完成、缺派生Receipt、不同请求同key、无关队列不影响、事件缺失与无变化派生零事件。该读取作为Dataset持久幂等记录下一步前置，尚未接实际Dataset，不算全链完成。

同轮补充ec_ingress_recovery.read_saved_projection_completion：从Journal完整保存清单读取，不接受外部传入派生子集；当前绑定/原run锁沿用。Store低层接口只证明所传命令集合，Dataset应使用Journal包装入口。

## Dataset不可变结果回执与稳定Build

2026-09-11，基线6841d170。新增a0v007 ecommerce_ingress_dataset_receipt，scope/run唯一、父Ingress FK、payload hash、不可变UPDATE/DELETE/TRUNCATE和FORCE RLS；复用a0v005不可变触发函数。data_os_store将既有Dataset+历史写入提取为调用方事务内部函数，原入口保持提交行为。新finalize_saved_dataset先锁run/核验当前绑定，从Journal完整清单核验基础派生及原事件pending=0，再同事务写Dataset元数据/历史和不可变回执。回执包含父/派生hash、固定完成时间、确定性Build ID与行数，连接成功退出后才发布内存。重试回读回执，不重写DB；Build使用同一ID/时间，内存丢失可恢复。

文件：services/aos-api/alembic/versions/a0v_007_ingress_dataset_receipt.py；aos_api/data_os_store.py、ec_ingress_recovery.py、新ec_ingress_dataset.py；tests/aip/test_a0v_ingress_journal_pg.py扩展真实PG组合。测试receipt失败使Dataset与历史回滚、投影未完成拒绝、成功后重复不新增Build、内存发布故障后从回执恢复、canary及不可变。既有Dataset事务专项回归。

不自动改变调度/DLQ状态；旧Dataset历史替换语义保持，运行回执单独永久保存，不以可覆盖历史作权威。调用方工厂须成功退出commit；public不迁移，实际调度/初始保存后续接入。Dataset当前展示可有后续批次，旧run重放不得回写旧元数据覆盖新批。

本轮最终核查修正无变化派生完成门：无新事件不代表有效派生视图已投影。通过相同身份/derived_revision/input_revision/input_hash/payload_hash的updated=true前序Receipt定位有效派生事件，必须计入pending；原“零事件即可”结论撤回。新增修改ecom_consistency_store.py及相应专项，避免Dataset先于有效派生视图成功。

## 实际调度原批次执行接线

2026-09-11，基线455e8b91。qyh_cron_scheduler在持久run claim后显式传durable_ingress=True，PipelineEngine仅该路径向executor传标记；标记只选路，不授予权限。ec_live_executor durable路径在任意源读取前核验running run/schedule/graph/source，并对实际执行nodes的id/type/config/pipeline与持久图及write_mode核对。原记录已存在时不读源/不重算；新记录以versioned源读得到的实际配置ref核验版本，共用既有transform，构建并保存基础命令和规范输入后提交，再调用既有恢复基础/派生、投影、Dataset finalizer。

文件：qyh_cron_scheduler.py、phase5_pipeline_engine.py、ec_live_executor.py、新ec_durable_executor.py；ec_ingress_recovery.py增加实际调用的合作取消/期限检查。保持旧非调度调用方式，后续统一其持久run；不增加公开API权限。新增单测验证选路、已有批次跳过源、新批次保存先于写入、版本/图漂移拒绝，回归调度与已有执行器专项。

边界：空源尚不能构造BatchCommand，必须明确拒绝而非制造可恢复成功，后续补无变更运行合同；辅助读取仍需完整来源版本证明；public未迁移，API未重载，不能声称真实调度运行已通过。调度失败后的原run重启claim仍需接续，当前只接首次持久run及显式恢复重入。

接线同轮发现CustomerLite聚合辅助读取仍使用字符串拼接且写aos.workspace_id而非canonical project GUC，失败返回空聚合。改用既有Store事务scope helper、过滤niushop/site1非删除订单，缺Store/读取失败抛固定错误；不得将读取失败算作0订单。新增聚合专项；其他辅助输入精确来源版本仍待后续验证。

## ignored基础项精确对账

2026-09-11，基线e585bdd2。不再把所有ignored作为同一种失败：校验原Receipt计数与命令数量、该事务实际写入Outbox计数；逐项核对当前基础对象/关系payload_hash与原命令完全相同，存活关系两端仍存在；按规范事件payload_hash寻找唯一已存在的权威基础事件，缺失/歧义拒绝。正常同版本同载荷重复可复用原事件，过旧被覆盖、缺关系、悬挂或缺历史事件不作为成功。

原批水位取这组精确有效基础事件max，不取当前租户max。完成统计必须包含重复项对应旧事件的projected状态，不能只统计本次写入事件。当前记录已被后来更新的旧批暂拒绝自动继续，需显式superseded对账；不静默用新对象替代旧输入。派生输入水位回退仍由既有CAS拒绝，不抬高版本绕过来源检查。

文件：services/aos-api/aos_api/ecom_consistency_store.py、ec_ingress_recovery.py与对应专项。新增正常重复、全重复仍待旧投影、混合新旧、过旧/缺Outbox/悬挂负例；SQLite先证据，PG组合后续。实际source为空的无变更合同仍单独实现。

实现核查：基础request_hash不包含idempotency_key，相同内容不同key可共享request_hash。改以既有event_key（含scope/stream/key/identity/outcome）统计本批实际写入，提取生成函数供原writer和对账共用；不得把request_hash当唯一事务身份。

## 派生写事务内基础版本门

2026-09-11，基线a277f15b。update_derived_metrics增加内部可选expected_base，验证其身份/type与派生命令相同且未删除；在既有对象FOR UPDATE之后、任何派生写入之前比较基础payload_hash。恢复入口从原父命令取对应对象传入，不接受调用者另造基础对象。已提交exact派生Receipt仍优先回读，不追加副作用；该前提属于事务执行门，不改变既有派生命令哈希/历史Receipt协议。

文件：services/aos-api/aos_api/ecom_consistency_store.py、ec_ingress_recovery.py；SQLite专项及新的tests/aip/test_a0v_ecom_store_pg.py隔离PG owner组合。验证外部预检后基础被更新时拒绝且无新派生Receipt/事件，匹配基础可写及exact重复回读，身份错配拒绝。恢复测试包装提交器透传expected_base，避免测试替身吞掉新门。

旧非恢复派生调用暂维持原接口；其他关联输入来源版本不由本对象hash替代。空批、重新claim、全运行验收仍待完成。不push，230 L0挂起。

## 已完成Dataset回执优先回读

2026-09-11，基线2bcc72da。现有finalizer先核验当前基础版本再读取已提交结果，使原批已完成后正常新批更新可能阻塞原结果恢复。调整为当前run/schedule/source绑定和完整原Journal校验后，先读取不可变Dataset回执；有回执只验证其hash及原父/派生hash，不重新判断当前基础/投影，也不写Dataset。无回执仍完整核验基础派生投影，pending不得成功。历史成功不代表当前对象仍为旧版本，不放松当前权限绑定。

文件：services/aos-api/aos_api/ec_ingress_dataset.py、services/aos-api/tests/aip/test_a0v_ingress_journal_pg.py。新增已完成后当前完成检查不可用仍可回读、保留新Dataset展示、源禁用仍拒绝；验证已有首次pending与原子回滚负例。此项先修恢复阻断；空批与重新claim仍后续施工，public不迁移、不push。

## 调度入口已完成运行回读

基线2aa865f2。ec_ingress_dataset.finalize_saved_dataset增加内部only_existing模式：锁run、校验当前绑定/原Journal后，无结果回执返回None且不对账或写入；有结果回执仍完整hash校验及提交后恢复缓存。ec_durable_executor在输入事务提交后调用该模式，有原结果则返回其行数及历史完成摘要，跳过基础/派生/投影；无结果沿原恢复链。返回completed_replay显式区别历史完成与本次投影处理；不把历史完成统计冒充本次处理数。

文件：services/aos-api/aos_api/ec_ingress_dataset.py、ec_durable_executor.py及tests/test_ec_durable_executor.py、tests/aip/test_a0v_ingress_journal_pg.py。验证已完成无源读取/无恢复/无投影、未完成仍按原顺序、无回执查询无写入、source禁用仍拒绝。只增加内部选路，失败run claim仍不放宽。
