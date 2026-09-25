# W5c8o｜隔离 PG 多组快照报告验证

## 基线与改动

- 方案 `m1@33a9a9fd`，承接 W5c8n `m1@722d4050` / AOS-000676；本波仅改 `services/aos-api/tests/extension_runtime/test_a0v_w5c8n_bounded_group_report_pg.py`。生产代码、迁移、真实库、Worker、ACK 均未改。
- 在完整 schema 的一次性 `aos_test_*` PostgreSQL 数据库中，保留原 12-member 保存组；另插入两个明示 synthetic 的缺输入组。新 Run、源 claim、组 claim/member 均通过原有 FK、唯一键、延迟完整性触发器和不可变表约束；没有禁用 trigger/RLS 或扩大权限。这两个 synthetic 组**没有原始输入**，只用于 `MISSING_INPUT` 分页与快照隔离，不能视为真实源组或回填授权。

## 新鲜验证

- 专项首次 `2 passed, 7 warnings in 228.79s`；复审加强原组 ID 严格顺序断言后复跑 `2 passed, 7 warnings in 224.82s`。
- 页大小 1：旧只读 RR 事务第一页 `READY_CANDIDATE`，第二页 `MISSING_INPUT`；在第一页后另连接提交第三组，旧快照依然只看前两组且末页无 cursor。新事务恰好看三组；旧 cursor 被拒绝。测试读取严格验证顺序为原组、第二组、第三组。仅一次命名 source fixture 调用，没有二次源读。
- 相关无 PG 累计测试 `82 passed, 7 warnings in 4.01s`；`git diff --check` 通过；隔离 `aos_test_*` 数据库残留 `0`。
- 浏览器/HTTP：本波无业务 UI；本机 `8080/docs` HTTP 200，`/health` 与 `/` HTTP 404，故不能宣称真实租户页面验收 GREEN。`aos-extension` profile 停止，只有 `aos-a0v-test-only` 运行。

## 方案/代码一致性与冻结门

- 与计划一致：仅测试 fixture/断言，不写生产代码；页顺序、同事务第二页、并发后旧快照不可见、新事务可见、跨事务 cursor 拒绝均有隔离 PG 证据。未测跨真实库、跨 Host、长事务超时与原 12 Run closure，均不得由本波推论。
- 真实库未迁 a0v_096/097，原 12 Run/Delivery Receipt 现时状态未重新读回；真实 profile 停止，真实 closure/回填/ACK 权限保持冻结。230 L0 挂起，不读商城源，`dev-org/dev-project` 只作零 canary；unknown 不重发、不手工 `run_definition`。
- 下一波 W5c8p：先设计受控 sidecar 回填 writer 的身份、不可变原输入绑定、RLS/权限及失败停止条件，另立真实读取门；在独立证据齐全之前不写真实数据或建 ACK。
