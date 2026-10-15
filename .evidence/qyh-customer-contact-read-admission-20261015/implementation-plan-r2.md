# 客户联系保存贡献：完整reader文件级方案r2

基线m1 90a601fd1ad2a57c128bf05416dbf97239412865、Authority2037。contact parent/maintenance-r10/signing/reader四Task同owner非重叠，至16UTC。产品v2/09、技术56-W6-08含8/25封板及原producer/Store/DDL/前端parser已复习。完整231Goal、原唯一真人安装全恢复本机授权与完整剩余经营首链/安装生命周期/八真实场景全部视觉/连续观察发布保留；原DB只读、HostworkerProviderOFF、unknown旧12不重放、disabledSchedule/source/noPush不变。daily每次实际aos最新m1同原卷全面PG→API→Web，aos2不重启，API-only不能替代。

## 基线证据与精确文件

90a601fd仅前置签名材料三文件代码：私有reason/原生产UTC纯签名重建/原Store私有序列化、敏感理由先于Store拒绝；原hash配方与公共wire/旧payload decode不改。冻结407/原w6_008临时PG往返/RLS/25006/真实in-process FastAPI输出和OpenAPI排除reason、新独立code r2 PASS合法消费；未部署、Task未提前Delivery。原实际API15265/source80b39、Web89803/f036及原卷schema161/650/绑定0不变。

probe-r2组合原W6-07与W6-08生产器：完整exact policy→原prepare/freeze→真实匹配frequency hash→reserved与skipped withdrawal sequence9/start10→unknown observation；原Start仍reserved、投影unknown保持held、签名不变。全部纯内存合成resolver，无DB/HTTP/实际Consent/Receipt/Contact准入。

另reader Task已登记两文件：`services/aos-api/aos_api/ecommerce_customer_contact_readonly.py`与`services/aos-api/tests/test_ecommerce_customer_contact_readonly.py`。parent只改`services/aos-api/aos_api/routers/ecommerce_workshop.py`与`services/aos-api/tests/test_ecommerce_workshop_read_http.py`；仅canonical `/views/customer/contact-contributions`使用typed ReadCatalog/installed readonly分流。正常legacy成功、其他GET/POST原门保持；原producer/Store/DDL/Web/AIP本reader阶段不再修改，额外文件先登记。

## 一致快照与完整计数

一个核实READONLY/REPEATABLE_READ/autocommitFalse连接，transaction_timestamp cutoff。SET LOCAL statement_timeout3000ms/lock_timeout500ms，查询间、解码循环与返回前monotonic10秒门。frequency policy全部保存修订COUNT与withdrawal全部观察COUNT保留，不去重/取样/截断冒充总数。固定两聚合返回count/invalid_count/MAX(created_at)，检查payload/outer tenant/id/revision/hash/date；withdrawal附加customer_id/consent_policy_id/sequence一致；createdAt/observedAt aware且与outer相同，未来MAX拒绝，不用WHERE cutoff隐藏坏行。SQL无效cast或任何错误稳定503，不补0/null；count原生int 0..2^53-1。未展示payload不声称全部逐行重算hash。

所有表/列来自固定常量。最新Start按created_at DESC/revision DESC/decision_id稳定排序LIMIT1；outer identity<=200/hash64/SQL CASE单行1MiB先于传输。单DTO1MiB/载荷总8MiB/总1280行，original start最多1000items。selected observations按原created_at/observation_id及revision确定顺序LIMIT257，超过256整视图拒绝，不截断历史冒充完整。reservation与skipped withdrawal每item互斥，最多1000见证行；bulk固定表参数化ANY或明确(customer_id,sequence)请求对，LIMIT1001且超界拒绝。query/row/size/循环均计入同一总门。

## 原保存物证验证

先验证未投影Start：private serializer与raw精确相等、strict int/bool/None不强转、outer tenant/id/revision1/batch_id/startedAt/hash匹配、aware且不晚于cutoff、全raw隐私检查含私有reason。reason缺失稳定`CUSTOMER_CONTACT_READ_SIGNING_MATERIAL_UNAVAILABLE`，不猜、不回填、不重放。调用已交付`customer_start_signing_hash`重建原生产UTC typed签名后比较，验证原decision_id派生公式、governance_prepared、原blockers、四zero。

精确读取Start.batchRef指定冻结Batch及其prepared前版、四policy，复用已交付`CustomerLifecycleReadonlyReader._decode/_validate_batch`与原policy签名/lineage合同，不改或复制源权威引擎；错误映射为本contact前缀。仅读取exact batch，不用当前latest替代。由Batch expected version/hash、Start exactRefs/私有reason及StartItem原模型重建校验请求；核完整eligible覆盖、itemHashes/customer refs、唯一有序items及八exact ref类型。Start签名重建在任何观察投影之前。

base items仅reserved/skipped_withdrawn。原typed StartItem/batchRef/exactRefs/startSequence重算bindingHash。reserved要求匹配原reservation ID/hash、tenant/customer/batch/frequency/sequence/createdAt、held状态及独立保存row，outer revision1/customer_id/policy_id/sequence/status一致；permit不可兑换、rawContactCount0、attempt prepared/providerCallCount0、各ID/bindingHash/outbox hash均按原producer；无withdrawal_sequence/actionReceipt/resolution。skipped要求sequence<=startSequence、无reservation/permit/attempt/receipt/resolution，并有同customer/policy exact refs及同sequence的已保存withdrawal witness，按原request JSON hash/派生ID/outer/date核对。只证明保存历史，不从现有事件猜当时所有撤回顺序、不重新判当前Consent或重算当前rolling-window配额。

读取exact frequency policy核原Create request JSON签名与ref；selected Batch/policy lineage按原合同核对，saved counts必须覆盖所选事实。观察逐条验证原RecordCustomerDispatchObservationRequest模型、完整raw/outer tenant/id/revision1/decision_id/item_key/date、原request hash/派生ID、exact原Start ref和存在且未skipped的item。unknown不能自解析；disputed resolution必须原模型允许且有typed ManualReconcileCase。保存typed ActionReceipt引用不当真实Receipt resolver已可用；原生产Start与ActionReceipt resolver仍恒拒绝，GET绝不调用它们、reserve_frequency、start、record或contact/Provider。

## 投影、隐私与失败

原Start和每观察验完后，通过纯已验证Store适配器调用原service.contribution_view，复用原覆盖items/ledger规则：输出仍是贡献投影，保留原Start contentHash，不将投影当新签名记录，不对投影重新签名；unknown保持held，不释放或重发。原Start对象不得被修改。公开wire沿用原模型，私有reason被排除；完整DTO重验、commands[]及permitRedemption/contactResolution/providerDispatch/send/external五false。敏感字段和值、任意扩展/缺字段/数字bool/越界/时间/租户/签名错误均拒绝；hash字段需先校验格式/原签名再排除手机号误判。不让异常补空/0成功。

## Loop与退出条件

独立方案Prime/合法消费后RED：原producer完整非空reserved+skip+unknown/manual-resolution、私有reason缺失/UTC重建、各hash/exact/lineage/outer/PII/数量/时间/超界/错误；新HTTP正常与installed只读空/非空/400/401/失败503/其他入口不扩权。最小实现后冻结专项/原W6-08/W6-07/相邻customer/price/closure/catalog；原w6_008与必要w6_007 DDL独立tmpfs PG真快照/完整COUNT revisions/RLS/25006/SQLCASE/privacy及准确停CID，独立reader与route质量。

精确提交后fresh维护-r10源冻结/原650 before/controller独立门/单新意图API-only；原真人正式SDK/拒绝矩阵/650全等、客户原稿适用三宽与只读交互/livePrime后才准确Delivery、Authority七强及全部remaining接续。前置签名Task一起按真实范围交付，不提前把代码或fixture当Contact/Consent/经营准入。完整Goal ACTIVE。
