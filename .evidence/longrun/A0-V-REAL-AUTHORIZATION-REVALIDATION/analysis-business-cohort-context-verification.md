# 原始业务样本组合验证

### SC4-5j3b 原始业务样本组合验证

AnalysisBusinessCohortContext以原pending Owner包裹原snapshot Owner，两analysisContext hash一致、需求cutoff等于组观察截止，窗口取真实需求；在原安装锁内读取SnapshotBusinessCohortPolicy导出并核version/hash/release/purpose，原完整outputs选择included/unknown/excluded，不删除raw或授予质量分数。结果绑定两个上下文hash与需求、样本策略ref/hash，消费后复验策略及输出，原Owner继续复验当前权限。

Red模块缺失，Green新增10 PG 36.09秒，原pending11+snapshot10回归21 PG 34.85秒通过（7warnings）。新增测试使用实际completed组/对象/Dataset回执，分析与pending为named doubles；原pending独立PG真实请求/暂停/取消及原snapshot10检查补充，不能合称真实完整首链。验证上下文/cutoff/purpose/策略类型和字节不符、消费中撤权/改策略/改输出/延迟被拒绝，重放source calls仍1。AR2扫描1932/188/93五类错误为空。

主库/安装/运行服务未变，未调用模型或外部业务能力。下一波SC4-5k1：设计并实现声明式逐事实字段联合计量，按业务cohort保留unknown分母，将每类必需公开字段与该用途required关系共同判定，分别输出12类事实观察/排除/有效计数，维度和近期统计明确区别；不能以type存在/行存在冒充有效事实，不将披露关系提升为强必需，不改legacy阈值。随后安装候选/Owner计量/正式QualityEvidence及Outbox消费者衔接。
