# AR2-7D D1 有界商品观察与规范版本比较施工卡

基线00494ba4/AOS-000571，沿用Task/Lease。已复习231-6 D1/数据履约及现有CoreObjectRecord.payload_hash、to_product、CanonicalPopulationReader。配置观察Evidence已保存，但不得把读取事件直接当经营事实。

## 本次范围

新增services/aos-api/aos_api/ecommerce_product_observation_comparison.py与tests/test_ecommerce_product_observation_comparison.py。

1. 宿主只读比较器接受HostTransaction/TenantScope、组合Evidence exact ref、原观察公开行及已绑定Channel/Entity/Binding exact refs。先读取组合Evidence并复验行摘要，再在repeatable read/serializable事务由既有CanonicalPopulationReader读取完整Product集合（99上限）。无新源读、无规范对象写入。
2. 每个源goods_id必须为正整数、site_id与观察相等，不接受bool/任意字符串；重复ID失败关闭，不能重复计数。规范Product六元身份须为同租户niushop、店铺ID恰为site_id的规范十进制文本；这里只支持实际Niushop商品规格，其他身份不猜映射。
3. 对当前每个规范Product按全六元身份与payload_hash精确SELECT，同事务重算CoreObjectRecord同构原始payload哈希（不做容错归一化），版本漂移或非法身份/类型拒绝。只输出公开title/price/stock比较计数，不返回额外properties；原混合source_updated_at不充当读取观察时间。
4. 分别报告源总数、规范总数、共同ID数、仅源/仅规范ID数与title/price/stock逐字段一致有效数。title非空原文精确匹配；price非负有限Decimal等值；stock非负整数等值；缺失/非法字段计为不匹配，绝不补默认值。字段数不冒充FactRevision，不生成QualityMeasurement或DataFulfillment。
5. 测试覆盖同ID内容不同、缺失对象、错店铺/平台/tenant、重复源ID、goods_id布尔、陈旧payload哈希、非法金额/库存、零分母和完整有界集合；真实SQL验证使用18434一次性库。新增reader SQL全部public限定。

## 退出与后续

这是固定比较Query的计算基础，不等于历史窗口覆盖、来源新鲜度、原归一化写入Receipt或业务履约。比较结果随后需由QueryResult/Evidence实际Owner持久化并绑定Requirement策略。秘密版本/连接身份/上游快照与JDBC日志门继续未知；不读真实源、不外发、不push，230 L0挂起。

## 写者合同复核纠偏

实际ec_ot_writer固定platform=niushop/shop=1，external_id=niushop:1:{source_pk}。本版仅支持site_id=1、严格按此命名空间比较，替代上文直接十进制external_id设想，不猜其它site映射。先独立read_bound核对物理店铺，空Product集合也不能跳过。追加ecommerce_canonical_population.py与ecommerce_business_investigation_case_selection.py仅public表限定，防临时表改变集合/选择Owner。

共同ID内每个字段显式分为match/invalid/mismatch三类，三数之和等于common_count。无对应对象仍计入only-source/only-canonical，不能从总体中消失。

闭包验证器正确识别新比较器为未分类反向调用方；将其按真实data query port去向加入closure-manifest.md，保留现有preHash和阶段验证规则。
