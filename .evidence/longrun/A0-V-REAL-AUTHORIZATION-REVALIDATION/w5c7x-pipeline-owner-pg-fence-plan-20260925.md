# W5c7x Pipeline Owner 可选 fence 隔离 PG 计划

## 上位与文件级范围

承接 W5c7w 的 default-off `PipelineControlServices` 钩子与 W5c5k/l 的 disposable PG Host lease fixture。真实库仍 `a0v_092`，绝不迁移或启用。仅新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c7x_pipeline_owner_fence_pg.py` 及本目录 audit/verification；生产代码原则上不改，若测试暴露实际 defect 则重新评估最小补丁。

## 九步

1. 复习 W5c7b/v/w 和 `consumer_connection` 事务/角色合同、`fence_case` 隔离 PG fixture。
2. 本方案先提交。测试只在 `aos_test_*` 库的 disposable public probe 表执行，显式 grant `aos_runtime`，不读商城源表。
3. 使用真实 `OptInHostLease.acquire` + 实际 `a0v_094` SQL guard，构造 exact scope 的 PipelineControlServices；仅将三个 Owner append/bind 的测试回调替为 probe INSERT，不伪造 guard。
4. 专项：有效 lease 下三入口同事务 commit；失配 epoch 下三个入口 guard 先拒绝、probe 0；Owner callback 写后异常整体回滚。核运行连接角色、scope 与无额外 source call。
5. 跑近期 A0-V 累计短回归；PG 测试单独会话避免已记录的环境顺序债。
6. 浏览器只读核 rev4/组停用，队列不冲刷。
7. 复审本测试只证明钩子到 SQL guard 的事务组合，不证明生产注入、完整 Owner authority、全机或外部 Store。
8. verification 落盘提交 m1，CAS 更新 docs 与 Prime 三投影。
9. 自动进入 W5c7y：业务 worker 中选择一个跨事务边界，先定位精确未知结果/Receipt 防重与 Host fence 接入方案。

真实 opt-in、closure、旧 attempt 重发与手工 run_definition 均禁止；230 L0 挂起、dev-org 仅隔离 canary、m1 不 push。
