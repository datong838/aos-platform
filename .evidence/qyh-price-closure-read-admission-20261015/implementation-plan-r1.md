# 价格闭环保存贡献读取：文件级方案

## 方案复习与边界

已读产品v2/08价格治理、技术57-W6-09含2026-08-25实施封板、原closure models/service/store/DDL、原creator readonly及测试、原price页面和parser。基线m1 804a0279，Authority2035，唯一owner原线程不变。完整231Goal、原唯一真人授权、daily/every aos最新m1同原卷完整PG→API→Web和aos2不重启保留。

本波只读取已保存price closure及usage/effect/handoff binding，不临时compile/bind/resolve source、不授运行或当前预算/审批、Handoff consume、Memory promotion。五轴独立；unknown usage保持null，immature不造完成，consumed不冒充accepted。原库READONLY/HostworkerProviderOFF/unknown旧12不重放/disabledSchedule不启用/source不读/noPush不变。

## 文件与归属

主Task已拥有`services/aos-api/aos_api/routers/ecommerce_workshop.py`、`services/aos-api/tests/test_ecommerce_workshop_read_http.py`、本E和原D-wave。额外同owner非重叠Task先登记两个文件及自身E：

- `services/aos-api/aos_api/ecommerce_three_module_closure_readonly.py`：在原CreatorClosureReadonlyReader中以固定类属性选择模块，共享现有hash/ledger/绑定校验；新增PriceClosureReadonlyReader子类固定PRICE，稳定price错误码包装。原Creator公开类、构造和默认read保持creator；没有来自query的模块选择。共享私有_row/_decode加默认creator的module参数，仍只允许creator/price。
- `services/aos-api/tests/test_ecommerce_three_module_closure_readonly.py`：原creator回归保留；新增原producer价格非空/空、模块隔离、五轴、strict raw、SQL门、敏感和失败场景。

不修改原domain producer/Store/DDL、AIP、Web/parser/CSS或用户dirty。route在原creator分支之外新增price分支，使用ReadCatalog的价格readiness typed installed readonly标记，才选择Price reader；原legacy成功、creator与customer及全部POST保持原门。任何额外文件先登记，不直接复制writer/客户端状态机。

## 共享算法与价格字段约束

现有64KiB单行SQLCASE、1MiB整体/DTO、只取最新closure和该closure下三binding的原视图语义保持（此视图没有全历史计数，不引入截断计数）。固定四表tenant双列参数、LIMIT1，created_at DESC与identity确定性tie-break；不以cutoff WHERE隐藏未来选中坏行。同一个已核实READ ONLY REPEATABLE READ连接，transaction_timestamp为cutoff。

价格专用入口在同事务固定SET LOCAL statement_timeout=3000ms/lock_timeout=500ms，查询间和返回前monotonic10秒门。价格SQL对外层identity/closure/source id作240字符CASE门，不传输巨大坏id；payload仍64KiB CASE，超限整体失败。creator原SQL/连接行为保持。没有分页或无界fetchall。

模块贯穿SQL参数、Compile request source类型、派生closure_id、row.module、DTO module；price sourceRef只能PriceDispositionRevision。binding外层module原producer可NULL，允许NULL或price；不能借creator closure/ref。closure hash仍原typed sourceRef/items经canonical_hash(default=str)，不改为model_dump另一算法；三binding按原payload字段与原typed refs签名/派生ID，exact closure ref、原_STATUS映射、_ledger守恒、时间与privacy沿用。

价格增加raw完整字段和递归strict int/bool/有限number检查，并要求完整typed model_dump JSON与raw相等，防默认值/coercion吞字段；usage settlement必须等于quality，符合原resolver和前端合同。保留未来immature cutoff合法状态，mature只沿原canonical成熟规则，不新建第二套成熟裁决。原public ResourceRef/HandoffResourceRef合同约束Task/TaskRun，拒绝任意扩展。前端parser全串拒绝mobile/openid/email/address/contactvalue/providerpayload，价格在后端也稳定拒绝无法公开的同类内容；不脱敏后冒充hash仍有效。creator既有正常行为与错误前缀保持。

Price子类只将原内部creator错误映射为PRICE_CLOSURE_READ_*，不吞异常补四null；正常空snapshot才四null+四真实缺口。输出沿原Service.contribution_view，再完整model_validate DTO，明确commands[]/handoffConsumeAllowed=false/memoryPromotionAllowed=false/externalEffectsAllowed=false。保存facts不提升当前source/Receipt/gate权限。

## 门禁与验收

先在本E执行原producer price非空四记录typed hash与五轴隔离probe；登记额外文件；冻结完整方案/原source/原DDL/原probe，独立Prime route PASS合法消费后才产品RED。RED覆盖price未准入/creator误读风险、正常/readonly分流、tenant/query/unknown admission、SDK形状和稳定非200；专项覆盖source type/outer module/ref/时间/hash/ledger/raw缺失/数字bool/unknown null/immature/request_more/隐私/SQLCASE及错误prefix。

最小实现后专项与creator相邻、原三module/价格处置/root/catalog冻结累计；原w6_009隔离tmpfs PG、原producer合成price与creator/foreign行、same snapshot、RLS/FORCE/25006/SQL超大NULL/隐私；独立代码和route质量。之后精确提交、fresh最新后端冻源/maintenance controller门/新意图API-only，原真人正常GET+正式price SDK、query400/匿名401、原650完整指纹不变、原稿三视口和现场Prime。准确两个slice Delivery/maintenance完整剩余接续/Authority七强，再下一登记helper。

不把隔离fixture、读取200/页面可见、测试或review PASS当经营首链。视觉比较保留真实空/unknown和禁入提示，不复制原稿47SKU或价格/异常。API-only读波不替代daily/every aos全面重启。回滚只撤price路由准入与本共享reader增量，需fresh维护门；不reset、不迁移原库、不覆盖dirty。
