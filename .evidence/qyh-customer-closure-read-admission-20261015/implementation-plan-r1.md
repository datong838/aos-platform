# 客户历史闭环贡献读取：文件级实施方案 r1

## Rules 与完整目标

本波服从231完整长程计划及231-6串行施工、228客户关系工作台逐区域产品规格、AOS工程交付闭环。唯一写者codex-01a13484-f019-7d82-94ce-812396db9124，Authority2038。原唯一真人安装/全恢复/本机管理员授权保留，不能代替预算审批。保护全部用户dirty与历史；原库只读、Host/worker/Provider OFF，不读商城源、不重放unknown/旧12、不启disabled Schedule、不push。原安装全生命周期、自然有来源CaseRun→建议exact评审→内容任务→权限预算审批能力→产物→真人评审续跑→总控Wiki、八场景及视觉、持续观察发布全部继续。每日和每次实际aos最新m1原卷全面PG→API→Web；aos-2不重启。本轮是Goal continuation，不冒充aos提醒。

## 已核对的问题与历史合同

当前HEAD f3dd116e9c753e94af91667bf13da4f544938945。客户closure-contributions仍通过旧CatalogDependency准入，达人/价格另有保存只读路径。共享reader明确拒绝CUSTOMER，不能只改枚举或批量白名单。旧服务contribution_view只调用latest_bindings；但旧Store连接不是强制只读RR，载荷无界，DTO缺省会暴露四个编译/绑定命令，不能直接接入安装只读分支。

原W6-09 compile通过原Store.resolve_domain_items把Start及当时observations转成原始status和canonical outcome，保存独立closure hash；后续usage/effect/handoff为独立保存绑定。contribution_view只展示这些保存记录，不重算当前Start，不调用resolve_domain_items/resolve_usage/resolve_effect/resolve_handoff或任何append/compile/bind。保存closure的sourceRef和receiptRef是历史声明，读取必须校验类型/hash格式/来源派生引用，但不声称重验当前Start签名、当前Consent、当前ActionReceipt或当前usage/effect/handoff权威；本接口不能解决生产resolver尚不可用。Start私有reason不是closure hash输入，也不能从closure猜测/回填。

closure hash原配方为canonical_hash({module,sourceRef,items})，closure ID由租户/module/sourceID派生；usage/effect/handoff按原服务payload配方校验hash与派生bindingID，绑定exact closure ref。沿用原_status、_ledger及保存快照语义：unknown不是成功，unknown usage.quantity=null，immature的未来cutoff合法，request_more不是accepted；五轴不能合并为经营完成。

## 文件与范围

新增 services/aos-api/aos_api/ecommerce_customer_closure_readonly.py 与 services/aos-api/tests/test_ecommerce_customer_closure_readonly.py，由新的非重叠reader Task登记后施工。不修改共享ecommerce_three_module_closure_readonly.py、原domain/Store/DDL/SDK/Web。
parent仅修改 services/aos-api/aos_api/routers/ecommerce_workshop.py、services/aos-api/tests/test_ecommerce_workshop_read_http.py 及当前D-wave/本证据目录。其他GET/POST/执行门、legacy成功路径保持。发现需扩围先登记方案和Lease。

## Reader实施

1. 单次connect_read_only(scope)，核read_only严格True、autocommit严格False、IsolationLevel.REPEATABLE_READ；SET LOCAL statement_timeout=3000ms/lock_timeout=500ms。一次transaction_timestamp取得带时区cutoff，monotonic十秒期限逐查询与decode后检查。
2. 固定四表/固定列/参数化租户及module=customer或exact closureID。每表ORDER BY created_at DESC,稳定ID LIMIT1，只选择最新保存记录；未存在closure时不查bindings。所有受限ID在SQL CASE最大240字符，JSON octet_length先给出原大小且CASE超过64KiB不传payload；最多四行，总1MiB。SQL只SET LOCAL和SELECT，不commit、不异常回退空/null/0。错误/超界稳定CUSTOMER_CLOSURE_READ_UNAVAILABLE/LIMIT_EXCEEDED/AUTHORITY_DRIFT/PRIVACY_UNAVAILABLE/CONTENT_UNSUPPORTED，不暴露原异常/PII。
3. 解码前确认outer tenant/revision严格整数1/created_at不晚于同cutoff/size严格正整数且限额。强类型raw整数布尔有限数校验，使用共享原严格检查（允许Task/TaskRun公开ResourceRef.revision字符串）；model_dump JSON与原raw全等，拒绝未知字段/宽松转换。调用共享CreatorClosureReadonlyReader._decode(...,module=CUSTOMER)复用原hash/ID/ledger/exact binding/typedpublicref/隐私检查，不调用共享read或PRICE分支。
4. 附加客户payload字符串隐私键拒绝（mobile/openid/email/address/contactvalue/providerpayload），receiptRef若存在必须ActionReceipt，原closure sourceRef必须CustomerBatchStartDecisionRevision；共享CompileRequest会重验该类型。对JSON递归/驱动深度异常RecursionError稳定LIMIT；其他解码或psycopg错误稳定拒绝，不能吞异常造空。所有行验证完成后才展示。
5. _SavedBindings纯适配交给原contribution_view(scope,CUSTOMER,now=cutoff)，重新验证完整公共DTO，allowedCommands=[]，handoffConsumeAllowed/memoryPromotionAllowed/externalEffectsAllowed均false；限制输出总字节并最终deadline。真实缺行产生原四blockers，保留原primaryColleague/atomic skills，不新建执行权威。

## HTTP接线

新增客户readonly factory/typed Depends。仅module=CUSTOMER的canonical closure-contributions GET使用ReadCatalog.get_readiness(module_id=ecommerce.customer)。验证typed readiness返回模块与principal双租户，query一律400。INSTALLED_ASSET_READONLY时才调用客户reader并map稳定503；正常legacy分支仍原service.contribution_view。anonymous原401，其他模块原路径不变；不调用任何POST/compile/bind/consume/Receipt/Contact/Provider。

## RED、验证与独立门

先新增RED tests证实当前缺reader与客户installed接线。使用原compile/bind纯内存生产器形成实际closure/binding hashes，覆盖非空unknown/immature/request_more、原TaskRef字符串revision；另用原Store.resolve_domain_items客户分支读取合成Start+observations证明状态映射（仅fixture，不声称生产Start真实产生）。空态/每行双租户/ID/hash/ledger/原ref/未来时间/不匹配module/非严格数值/未知字段/同cutoff/RR/read-only/SQL参数/单行限额/深度/超时/隐私/错误不补零均需验证。HTTP含typed错模块和错tenant拒绝、非安装legacy原样、达人价格回归。

冻结HEAD Git归档仅叠加四owned代码，不混dirty/.env；专项及原共享reader/三模块domain/客户contact/lifecycle/HTTP相邻累计。原w6_009 DDL自有tmpfs PG验证真实JSONB、SQL/RLS/25006、snapshot并发、空记录与非空原生产器，不迁移原卷；准确CID停止。冻结代码独立Prime质量PASS合法消费后精确提交。

后续维护Task独立fresh冻源/原650 before/controller独立门/单次意图API切换，原真人正式SDK/400/401/无业务非GET/650全等、1280x720/1440x900/1920x1080客户原稿同尺寸比较及独立现场复审后才Delivery/Authority/Prime七强。保留导航密/横幅占首屏/中央任务计划进度日志/右侧产物分层360/宽屏空白及语义过强等视觉待修项，不填演示4207客户/67人任务。不得重做上波已交付contact验证冒充本接口证明。

## 风险与回滚

主要风险：把历史绑定当当前运行授权、哈希在datetime解析前后不一致、ResourceRef字符串revision误拒、unknown/成熟度/请求补充被合并成成功、错误伪装真实空态。均以原typed配方与真实fixture/native反例约束。只限读取slice，不能声明业务/安装/八台视觉/完整Goal完成。回滚仅撤去本canonical安装只读分支及独立reader，不改原数据/生产Store；部署前受维护精确门控制。
