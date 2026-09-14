# SC4-5e2 显式观察时间映射v3

2026-09-14；基线cc57d3bf；A0-V-SC4-FULL-STORE-SNAPSHOT；m1不push。

新增pipeline_snapshot_materialization_v3.py，原入口仅增加版本分派。v3必须声明observation时间与row-presence-only删除口径；根据实际选中整数字段解释状态，保留原范围/字段/身份/整批拒绝规则及精确decimal。输出updatedAt/observedAt为观察版本时间，sourceUpdatedAtBasis=observation、sourceModificationTimeKnown=false，不生成源修改时间；原始业务字段仍保留。物理缺失不变成删除。

观察元数据及其时区保留字段禁止调用者覆盖；保留微秒精度。旧Product事件读入类型仍v1/v2，未扩展新触发授权。带软删/关系旧执行声明仍不支持，先供Category，其他对象需单独处理。

84 passed/7既有警告/4.83s，涵盖v1/v2/v3与SKU候选。新v3验证真实canonical normalize、显式未知源时间、状态变化、空观察、精度、精确数值、跨店/额外列/重复/未知状态/伪造时间或时区/物理缺失删除口径拒绝。全部合成静态测试，无主库写入。首轮6缺v3分派失败、后续规范时间格式断言差异修正，未放宽原UTC规范。

AR2 1909扫描/187分类/93迁移、五数组空；memory GREEN1105/1088/2709；diff-check通过。没有新安装候选使用v3，未做真实SourceReadiness/Fulfillment。后续质量和分析必须尊重显式观察语义，不能据source_updated_at推断源历史修改时间。

下一：分类快照候选及层级完整性检查；订单显式软删和观察版本策略，随后剩余对象、关联与实际采集补齐。主首链与八场景仍未完成。
