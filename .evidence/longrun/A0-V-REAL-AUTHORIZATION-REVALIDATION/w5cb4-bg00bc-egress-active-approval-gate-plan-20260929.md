# W5CB4 BG-00bc｜Egress 新 active 审批禁入

## 上位合同与 Rules

231/231-9 要求真实批准、当前策略与 Receipt，不以 `approvalRef` 非空代替批准。BG-00bb 已证 Egress 新 active 可在无 maker/checker reader 的 Store 写入。当前库只读、Host/worker/Provider关闭；本波只修该 Store 新 active 路径，不动 Data/Quota/Budget、schema 或历史记录。

## 文件级步骤

1. `tests/aip/test_aip_runtime_guard_policy_store.py` 加 test-only RED：只有 `approval:test` 的新 active Egress 应拒绝且无 Revision/Receipt；草稿提交/回读、既有 active 精确读取保留。
2. `aip_runtime_guard_policy_store.py` 在同请求幂等 Receipt 回读后、新写入前，以专用错误拒绝 Egress active；数据分类路径不在本波变更。
3. `routers/aip_runtime_guard_policies.py` 将该错误映射 422 中文消息。
4. 下游 `test_aip_network_policy_store.py`、`test_aip7_model_runtime_store.py` 使用隔离临时 PG 的历史 Egress fixture 核验既有消费门；不能用测试夹具主张正式批准。
5. 专项/相邻回归、diff/编译复审、verification、精确 m1 提交、上下文更新；后续正式审批 reader 同事务消费另立波次。
