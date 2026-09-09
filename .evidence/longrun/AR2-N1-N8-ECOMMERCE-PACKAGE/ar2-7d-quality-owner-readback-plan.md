# AR2-7D D1 质量证据 Owner 精确回读补强

基线91fd9559，沿用231-6 D1质量Evidence施工卡和当前Task/Lease。Rules：m1串行、方案先行、最小修改、自测和本地独立复审；不push，230 L0挂起。

修改文件：services/aos-api/aos_api/data_requirement_quality_evidence.py、services/aos-api/tests/test_data_requirement_quality_evidence.py。

后续DataFulfill必须从真实质量Evidence Owner回读；当前读取使用未限定表名，且正文仅Python结构等值与重建后摘要对照，不能识别false/0、true/1等原始JSON差异。新增原始payload canonical_hash与原内容地址校验，同时保留重建正文/拆列验证；INSERT、SELECT和撤销查询明确public权威表。既有合法payload和hash计算不变，不扩大事实覆盖或添加调用权限。

先加原始JSON类型替换反例（需求piiAllowed为false时被0替换）确认旧代码失败，再修复。真实PG临时同名Evidence及撤销表遮蔽反证：写入仍到public，临时伪撤销不能阻止真实回读，public撤销不能被空临时表隐藏。沿用18434自有一次性数据库，串行测试质量评估器/证据与旧查询分支，回滚/租户/并发/撤销回归。

本切片不认证测量来源、不创造Product事实、不满足完整DataFulfill，不推进AR2_7D整波GREEN。
