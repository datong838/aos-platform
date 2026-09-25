# W5c8r｜见证写门拒绝矩阵补证与离线部署审计

## 基线与范围

方案 `m1@38c39727`，承接 W5c8q `m1@7c609e6e` / AOS-000679。本波仅扩充 `services/aos-api/tests/extension_runtime/test_a0v_w5c8q_witness_backfill_gate_pg.py`；`a0v_098`、权限 grant、应用代码均未改。真实 profile 未启动、真实库未迁、未读商城源或真实历史。

## 新鲜结果

- 完整隔离 PG 专项 `2 passed, 7 warnings in 118.07s`。除 W5c8q 正例/并发外，新增直接验证：superuser session 即使 `SET ROLE operator` 也拒绝；非超权 caller 若未显式 `SET ROLE` 则拒绝；`READ COMMITTED` 而非 RR 拒绝；租户 GUC 清空拒绝。这些均未插新 sidecar 行。
- 相关无 PG 累计 `82 passed, 7 warnings in 4.00s`；`git diff --check` 通过；隔离 `aos_test_*` 数据库 0、临时 `aos_test_witness_*` caller 角色 0。
- 全仓调用点只见 migration 与测试，未接应用运行路径；`8080/docs` HTTP 200 只是本机可达，业务浏览器/真实租户不具备验收条件。`aos-extension` profile 停止，`aos-a0v-test-only` 运行。

## 方案/代码一致性与未证

- 本波按方案只增拒绝测试，无生产行为和权限扩大。原 claim/input/member 不可变，不能通过篡改真实原行伪造 member/actor 漂移；现有隔离 fixture 对此未建一组“合法提交但恶意自洽”的历史输入。该矩阵仍未证，不能称全量校验已覆盖。跨真实 Host、长事务/资源预算、旧库迁移顺序和真实数值歧义同样未证。
- 真库未迁 096/097/098，原 12 Run/Store/Delivery/Host 现时证据未知；函数即便隔离 PG GREEN，也无应用 operator 成员与执行授权。历史扫描/回填/ACK/closure 继续冻结；unknown 不重发。
- W5c8s：先做真实 profile **只读重启及迁移前门的方案与清单**，同时补历史恶意自洽输入的隔离 PG 构造可行性；没有独立证据和权限闭环前，不实际迁真实库或授 operator。

230 L0 挂起、商城源不读、dev-org 零 canary、m1 单写不 push。
