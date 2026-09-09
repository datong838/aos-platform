# AR2-7D D1 商品逐行联合计量验证

2026-09-09，基线64c490d8；m1串行，18434自有隔离PG，无真实源/Provider/发布/push，230 L0挂起。

- 初始联合计量专项18 passed（3.76秒）。三选择ref布尔修订反例真实DID NOT RAISE（/tmp/ar2-product-joint-ref-red.log）；第一版JSON摘要修复仍1 failed/49 passed，因为Pydantic StrictInt|StrictStr的JSON序列化会将修改后的True转为1。
- 最终显式校验ref/revision实际类型，比较python原值摘要；同一反例已通过。新增测量时钟不能早于观察结束反例。联合计量、旧比较、组合Evidence三文件最终50 passed，4.89秒，/tmp/ar2-product-joint-green2.log。
- 相同字段边际数对应不同联合有效数实测；坏值/缺身份留eligible，明确状态先过滤，重复候选ID整组隔离，顺序不影响计数；0人口、时间、scope/ref/rows/spec、撤销与纯SELECT均通过。
- 本地独立只读终审无阻断项，非外部Prime。实现SHA-256 7547d3fca0b31f71f6f73c46581ab99a09b64c26285af963fdbef0105f52d46a；测试1c68f203431989f947f10a4aaa2ad6b9bb492cb853487bd94a24d3d36f83cf45。
- 闭包ar2-1扫描1703/分类89/迁移57，五类错误空，diff --check通过。方案与实现一致。规则是公开源行结构计量，不认证Category外键、规范一致、历史窗口、完整Product事实或Requirement满足；AOS-000571不前推。
- 下一项复用实际MetricDefinition/QueryResult保存联合计量及其规则、观察谱系，保持partial/unknown；随后继续规范版本核验及需求策略，不能直接造履约成功。
