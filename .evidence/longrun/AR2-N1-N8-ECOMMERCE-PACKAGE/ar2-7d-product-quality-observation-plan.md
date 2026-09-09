# AR2-7D D1 商品质量输入观察规格

基线93477f5f；Rules沿231-6 D1，同Task/Lease，m1串行、先方案再编码。复习P02实际mapping与ec_normalizer：goods_state决定上下架、category_id为分类、create_time/modify_time为原始业务时间。旧_normalizer会填默认值，不能充当原始字段实测。进一步核查_clean_rows：具体行为为删除is_delete==1行和0时间转None，并非普遍丢弃非法价格；前一验证文档“坏行”表述在此精确限定。

## 文件

维护services/aos-api/aos_api/source_read_observation.py、ec_source_adapter.py、ecommerce_product_observation_comparison.py、ecommerce_product_comparison_query.py；维护tests/test_source_read_observation.py、test_ec_source_observation.py、test_configured_source_observation_evidence.py、test_configured_source_observation.py、test_ecommerce_product_comparison_query.py。

## 合同

新增固定spec niushop.product-quality-observation/v1，对应cleaningVersion niushop.product-quality-fields/v1。沿现有SourceReadObservation envelope增加允许的明确spec/version配对；历史niushop.product-observation/v1和默认cleaningVersion原文不变，无新增领域Owner或迁移。新spec必须excludedCount=0，retainedCount=fetchedCount；只代表保真投影，不声称行合法或商品事实完整。

复用原两个有界读取入口及配置输入绑定：仍仅ns_goods、正整数site_id一个过滤项、无cursor、LIMIT101超过100整个拒绝，现场返回跨site行整个拒绝。公开字段固定goods_id/site_id/goods_name/price/goods_stock/is_delete/modify_time/create_time加goods_state/category_id；不带legacy无来源state字段。新spec不执行_clean_rows，不删除软删/下架行，不改0/空值、不填默认值、不去重。坏值、缺字段及重复商品在原始行hash中保留，供后续固定规则明确eligible/excluded/duplicate/valid；非有限数/不支持的值仍整个观察拒绝，绝不静默丢行后报完整。PII/任意额外列不返回、不持久化。

spec与cleaning配对由冻结映射校验，新旧不能混配。原固定三字段比较/Query显式只接受旧spec，不能把新输入重用旧policy标签；v1原合法hash、读回和查询保持。新观察复用已有配置和观察Evidence持久化，仍factIds=[]、upstreamSnapshot/connectionIdentity未知。尚不产生质量分数、Product覆盖或DataFulfill成功，不接真实源。

## 验收

连接器只使用测试替身：新规格保留软删/下架、0时间、缺分类、非法price、重复ID；公开字段白名单、scope/100-101、旧清洗行为、显式spec/version拒绝。真PG：新组合Evidence往返/撤销/外层回滚、旧规格Query拒绝新输入；现有观察/配置/Query回归串行18434。闭包、自洽检查与本地独立复审，证据后提交，不push，230 L0挂起。
