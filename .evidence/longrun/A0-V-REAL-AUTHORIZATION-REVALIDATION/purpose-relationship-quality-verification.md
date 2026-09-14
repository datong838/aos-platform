### SC4-5i2 用途关系质量计量验证

新增 pipeline_snapshot_relationship_quality.py：策略exact绑定原关系policyHash，逐用途完整列出required/disclose，禁止漏项/重复/未知/全disclose；执行时重编译防篡改。复用原完整cohort/key/重复/容量/关系策略检查。每规则observed=excluded+eligible，仅显式删除行排除；活跃行缺客户仍保留分母。多个引用全部存在且父未删除才complete，allowUnset单列；缺失/非法/删除按行计数并仅一次incomplete。返回用途所需缺口、应披露缺口、空分母规则，不产生ready/Fulfillment或改旧阈值。

Red先确认模块不存在；18项新增测试5.20秒通过；连同原关系和正式DataRequirement质量测试共82项4.85秒通过（8个既有运行警告）。订单185/有效125/客户完整98/缺27是基于已核验聚合计数构造的测试，不冒充再次源读。AR2 ar2-7扫描1926/187/93，五类错误为空。无源连接、数据库、安装或业务副作用；主库仍未升级。保护9月13日进度用户改动。

下一波SC4-5i3：从冻结1.17生成1.18候选，新增声明式用途关系质量策略及静态执行评测。initial_store_analysis对Order.placedByLite与ProductReview.byMember披露但不剔除事实，其他12关系必需；customer_cohort_analysis要求全部14关系，不代表该业务Profile已注册或允许动作。旧1.17、12映射、原source-quality元数据策略与首装DataRequirement保持不变；没有签名安装/正式就绪资格。随后SC4-5i4从当前包Owner绑定该导出策略和原快照，避免外部自报计数。
