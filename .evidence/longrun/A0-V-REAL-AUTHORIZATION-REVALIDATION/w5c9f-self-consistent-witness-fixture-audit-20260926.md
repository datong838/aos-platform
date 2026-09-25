# W5c9f｜恶意自洽原输入夹具审计

方案 `m1@36e6ead6`，隔离 PG 夹具清单补充 `m1@3bbae34e`。静态审查 `a0v_045/097/098`：原 input 的 deferred trigger 精确核成员数/runId/原 ingress envelopeHash，并对 rowsHash/rowCount 验格式与范围，但不证明这两个字段与真实行内容一致；`a0v_098` 主要固定原 claim/input/member 的 canonical 字节与哈希，不等于业务行真实性/ACK/closure 授权。真库未迁 096/097/098，应用无 operator 授权。

新增仅一次性 `aos_test_*` PG 测试：从隔离 fixture clone 新 run/source/ingress，保留准确 envelopeHash；为独立新组提交 manifest，将 rowsHash 改为合法格式的零哈希、rowCount 改为与原 fixture 不同且合法的数值，并重新计算 manifestHash。`pipeline_snapshot_group_input` 及其 deferred trigger 接受并提交，读回原样且哈希一致；对应 canonical sidecar 行仍 **0**，未调用 `a0v_098` writer。首轮 RED 是测试 helper 使用 call_ordinal 700 违反 `pipeline_controlled_source_claim` 真实 CHECK；改为合法 2 后专项 `1 passed, 7 warnings in 113.86s`。这证明“历史原输入合法且自洽”不能独自证明 rowsHash/rowCount 业务真实性，不宣称 writer 接受/拒绝该组。

隔离 PG `aos_test_*` 数据库残留 0、`aos_test_witness_*` 临时角色残留 0；`git diff --check` 通过。真实唯一恢复 PG/18181 PID28077/8080 job 边界未变。未读商城源数据、未迁真库、未回填/ACK/关闭原十二 Run。下一波 W5c9g 在隔离 PG 精确测试 `a0v_098` 面对该类输入的行为，并明确定义 canonical witness 与 semantic authority 的分层；不能以此测试给真实 effect 授权。
