# 客户贡献保存读取：文件级实施方案

## 基线与军规

基线m1 7385617635ab7331483ad6e891e8bf5e089839e5、Authority2036、同owner customer-contribution-read-admission和maintenance-r9至08UTC。已复习产品v2/09、技术55-W6-07含Aug25实施封板、原models/service/Store/w6_007和前端parser。完整231Goal/原唯一真人授权/daily每次aos最新m1同原卷全面PG→API→Web/aos2不重启保留。

只读已保存Consent policy/Segment/Journey/Dialogue修订计数和最新Batch。CustomerLite ref不是ProtectedContact，历史granted/evidence不证明当前Consent/retention/purpose或可联系；不调用prepare/freeze/create/resolver，不读商城源、不解析contact、不start/send/Provider。原生产external policy resolver恒拒绝，读取不解除它。原业务DBREADONLY/HostworkerProviderOFF/unknown旧12不重放/disabledSchedule不启用/noPush、不覆盖用户dirty。

## 文件与登记

parent已拥有router与read_http、本E、原D-wave。另Task先登记：

- `services/aos-api/aos_api/ecommerce_customer_lifecycle_readonly.py`：新专用reader、原typed请求及hash验证、同snapshot完整计数/选中batch与exact ancestry、尺寸/隐私/时间/稳定错误。
- `services/aos-api/tests/test_ecommerce_customer_lifecycle_readonly.py`：原producer fixture、metadata/完整counts/strict raw/typed hash/lineage/未知同意/零效果/失败门。

parent只改`services/aos-api/aos_api/routers/ecommerce_workshop.py`与`services/aos-api/tests/test_ecommerce_workshop_read_http.py`，仅canonical GET `/views/customer/contributions`用typed ReadCatalog installed-readonly分流。legacy成功及全部POST、contact/closure辅入口不改；不改原producer/Store/DDL/Web/parser/CSS/AIP或锁文件，额外文件先登记。

## 一致截止面与完整COUNT语义

原counts是四表全部已保存修订的COUNT(*)，不是distinct identity、活跃同意人数或逐行政策有效性背书；保留完整计数，不设截断取样后冒充总数。用一个已核实READ ONLY REPEATABLE READ连接和transaction_timestamp cutoff。固定statement_timeout3000ms/lock_timeout500ms，查询间及返回前monotonic10秒门。

四个固定COUNT SQL仅返回count、invalid_count、latest_created_at。invalid_count检查outer id长度、payload tenant/id/revision/contentHash与外层对应及createdAt有时区且与外层时间一致；无效时间cast失败亦稳定非200。MAX created_at超过cutoff拒绝，不加WHERE时间条件隐藏未来坏行。COUNT不向客户端传输policy payload，不执行全表fetchall，也不声称重算过所有未展示policy的content hash。返回count必须原生int、0到2^53-1；任何错误整视图失败，不能补0。

最新batch用固定表、tenant双列、ORDER created_at DESC/revision DESC/batch_id和LIMIT1，SQLCASE先限制单行1MiB/outer id200字符。frozen再读同id exact前版；selected batch的consentPolicy/segment/journey/dialogue四exact refs各取固定表一行。合计最多6payload行/8MiB，DTO1MiB，所有查询有界且同snapshot。没有batch时仍返回可信四COUNT，不读无关policy载荷。batch存在则各对应count至少1。原计数包含所有修订，例同policy rev1+rev2计2；exact旧refs仍定位旧版本，不强制最新policy。

## 选中事实与原签名

每payload完整字段/strict int与bool、None只在原nullable合同处、原model_dump JSON与raw一致，outer tenant/id/revision/hash/created_at与payload匹配且不晚于cutoff。selected四policy重建原Create request JSON核content hash及exact ref，核segment→consentPolicy、journey→segment、dialogue→journey/eval一致。只作保存历史lineage，不启动当前授权resolver。

Batch用原Prepare request模型校验1000项以内、itemKeys唯一、CustomerLite类型、eligible consent/retention/k/evidence及非eligible理由，逐项重算itemHashes和五桶ledger。bindingHash按原typed refs+itemHashes，经原canonical_hash(default=str)；prepared contentHash按request JSON+typed CustomerDialogueBatchLedger对象+bindingHash，不能改用JSON ledger。prepared只能rev/version1/priorNone；frozen必须exact prepared前版、rev/version递增且所有七字段排除后的继承内容相等，再按原完整payload签名。无已识别stale writer则拒绝，不猜新签名。contactResolution/action/providerCall/send/externalEffect五counts必须原生int0。

全部输出相关字段及selected policy通过原redact_sensitive与前端禁披露字段门，typed hash单独验证后排除其误判为电话；拒绝PII/任意扩展而非脱敏后假称原hash仍有效。不给raw message/Provider payload/成员PII披露。最终复用原contribution_view的Skill/Logic/数字同事/阻断布局，输入是已验证的纯保存适配器；完整DTO重验，commands[]及contactResolution/start/send/external四false。DB/validation/limit/privacy错误稳定503，真实空才0/null。

## Loop与门禁

先本E原producer纯内存probe（修正原测试approximate ref为完整exact hash），核6个typed refs、typed ledger签名、prepare/freeze继承、eligible/unknown及零效果；明确内存resolver非生产权限。独立方案Prime PASS合法消费前不改产品。

RED含原404/异常补0风险、计数全修订/同snapshot/未来坏行、batch两生命周期/引用旧policy、raw缺字段/数字bool/隐私/unknown不造eligible、SQLCASE及稳定非200；实施后专项/原W6-07及相邻price/closure/catalog冻结累计，原w6_007隔离tmpfs PG/COUNT rev2/并发快照/RLS/25006/SQLCASE/privacy，独立reader和route质量。精确提交后fresh维护freeze/controller门/新意图API-only、原真人SDK/400/401、原650全等、客户页三视口原稿/核心只读及livePrime、准确Delivery/Authority七强/下一登记helper。

回滚只撤该GET准入及专用reader增量，经fresh维护门，不reset或动原库。API-only不代替daily全面重启；真实Consent/预算/自然经营首链/安装全生命周期/八真实场景全视觉/观察发布仍未完成，不以页面/测试/fixture或PASS收窄完整Goal。
