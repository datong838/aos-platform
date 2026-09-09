# AR2-7D D1 联合字段计量 QueryResult

基线9c4fc15f，沿231-6实际Metric/Query Owner合同与当前Task/Lease。m1单人串行、不push，230 L0挂起。

## 文件

新增services/aos-api/aos_api/ecommerce_joint_quality_query.py、ecommerce_fixed_metric.py及tests/test_ecommerce_joint_quality_query.py；维护ecommerce_product_comparison_query.py（仅提取共用固定Metric写/read helper，原定义、hash及Query逻辑不变）；登记closure-manifest.md。

## 实现

固定MetricDefinition niushop.product-public-row-quality-counts/v1保存原public.aip_metric_definition_revision，unit=count、window=source-read-interval、aggregation=public-fields-joint/v1。从已有ProductJointQualityReader取真实计量；不接受调用方counts/rule/SQL。共用helper严格只访问固定public Metric表，复用原Owner append规则，核验完整原定义与hash；预期定义来自两个固定服务代码，非外部命令。保留旧通用Metric Store自定义schema行为。

新Query服务只接受HostTransaction/TenantScope及组合Evidence/公开rows/Channel/Entity/Binding refs、key/actor。scope+固定operation+key advisory xact锁，原QueryOwner create/record_result，同事务提交；重放重新核对rows hash与已保存Query，不重跑计量或源连接。规则来自固定执行模块，原请求filters存完整四refs与规则identity/revision/contentHash，严格校验ref实际revision类型以免JSON归一化bool。窗口严格actual readStart/readEnd、cutoff=end；零区间拒绝，deadline=end+1day，过期新执行拒绝；旧事务冲突须整体退出后上层新事务reconcile。

八行identity/title/availability/category/price/stock/createdAt/updatedAt；每行显示相同observed/excluded/duplicate/eligible/distinctPopulation/jointValid及该组fieldValid。joint是实际逐行AND的保存结果，不能在read_exact用边际数重建。SourceRef仅组合观察Evidence（unknown），lineage为实际Metric+三选择refs。QueryResult固定partial，confidence不评分，明确未证明历史快照、规范库一致、Category外键或Product经营事实覆盖，QueryJob成功只表示计算完成。

read_exact回读实际Query、Metric和组合Evidence撤销；原request_json/result_json摘要与规范DTO对照（历史Query hash不变），固定规则/窗口/deadline/列/8行/来源谱系/flags全部对照。数值严格int0..100，observed对照观察fetched，分区等式、0人口、duplicate若非0至少2、joint<=每组fieldValid、identityValid=distinctPopulation<=eligible；不能用这些结构检查宣称重新验证原行。历史回读不扫描现在的规范库。

验证：真PG持久化/精确回读、同key不重算、输入或actor漂移、外层回滚、并发旧事务冲突/新事务重放、canary、观察撤销、原JSON布尔篡改、伪规则/refs、空人口、零窗口；旧固定Query+joint计量邻接回归、闭包、本地独立终审。仅18434自有一次性库，不运行真实源/Provider或迁移新表。不注册不完整DataFulfill、不推进AOS-000571。

独立复核补强：joint还须>=max(0,sum(fieldValid)-7*eligible)，这是集合交集必要下界，不是从边际数恢复真实AND。单行八组全部有效但joint=0的返回正文注入反例先实测DIDNOTRAISE，再修复；真实表的触发器保护不移除，权限拒绝后按既有只读注入方式测试。
