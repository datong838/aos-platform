# 商品内容准备查询接续

2026-09-11，基线6bfbdba4，AOS-000573。沿用产品07/12、技术15/101/231-5/231-6：来源精确、未知不当零、不得为通过D01而伪造ready。

新增 `services/aos-api/aos_api/ecommerce_product_content_query.py`：受信宿主内部固定查询，输入已保存商品Evidence，读回与重算先验证，按首次快照输出observed/eligible/jointValid/preparable四项固定计数。固定MetricDefinition通过既有Owner注册；QueryJob/Result通过既有Owner/Receipt保存，同事务不提交，稳定幂等；读回复算完整请求与结果，不只验证引用。结果保持partial、来源freshness=unknown，明确源连接身份和上游新鲜度尚未验证，因此目前不能作为D01 ready事实。不得把新鲜度缺口改成fresh绕过当前门禁。固定查询支持完整观察的零计数，但不生成ready AnalystMetricValue。

新增 `services/aos-api/tests/test_ecommerce_product_content_query.py`：显式一次性PG，正向计数与重放、原证据撤销拒绝、租户隔离、事务回滚；共用商品证据与既有QueryOwner回归。无迁移、主库写入、Provider调用。

下一项仍须补齐正式源连接/新鲜度/质量与reconciliation事实，才可让经营参谋自动生成真实计划。本波只建立无需手工转写数字的固定查询通道，不声称首链完成。
