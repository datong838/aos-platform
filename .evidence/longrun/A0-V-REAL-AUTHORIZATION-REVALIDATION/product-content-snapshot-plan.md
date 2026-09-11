# 首链商品内容准备候选聚合

2026-09-11，基线8b169ab7，AOS-000573。真实验收矩阵经营参谋→内部内容任务需要真实商品事实；不得用销量未知的商品宣称热销或增长机会。只读主库核查org-org/dev-project/niushop/1当前active规范对象各类计数为空，不能当成实际源商品数0；真实源尚未恢复。

## 业务口径

本波建立固定“内部商品介绍准备候选”计算：复用完整商品quality observation（当前最多100行，超过拒绝，绝不截断）。排除明确删除/下架；重复正整数goods_id全部隔离；逐行复用既有八项joint quality规则。仅八项均有效且库存正数的商品进入候选；按库存降序、goods_id升序确定最多5项，并明确不是销量/收益预测。保留实际候选总数与返回数，Top5只是展示候选，不篡改全量统计分母。

输出完整观察/排除/重复/eligible/identified/qualified/可准备商品计数、原质量版本/观察exact ref、候选原始商品ID/标题/库存及原行hash。价格只参与既有质量检查，不输出缺少正式币种依据的价格文案；不猜销量、转化率、涨幅。空或异常记录保留原因与质量统计，不生成0增长/0转化等指标。该快照不是完整MetricValue ready，也不是Insight/批准计划。

## 文件

修改 `services/aos-api/aos_api/ecommerce_product_joint_quality.py`：把已有逐行八项规则抽成函数供原计数和本波复用，保持旧计算行为。
新增 `services/aos-api/aos_api/ecommerce_product_content_snapshot.py`：内部同HostTransaction/tenant/当前shop selection与ConfiguredObservation exact读取，复用ProductJointQualityReader后生成固定候选快照；禁止未经authority验证的数据入口公开。
新增 `services/aos-api/tests/test_ecommerce_product_content_snapshot.py`：完整分母、重复隔离、错scope/原文漂移、缺字段/零库存、确定排序/Top5、布尔/超大库存、无价格和营销推断字段；复用既有quality/observation测试与隔离库支持时验证。

## 边界和后续

本波不放宽100行原始观察上限或99规范对象上限，不宣称大规模聚合已经支持；首链实际数据规模需真实源恢复后核验。后续必须补分页/聚合快照来源合同，不能直接调大数值冒充完整性。快照由正式宿主读取流程接入，不允许手工补Row/Query/Brief完成真实验收。下步保存可披露快照与正式Metric/质量/Query，接回D01/计划首链。无主库写入/Provider、不push，230 L0挂起。
