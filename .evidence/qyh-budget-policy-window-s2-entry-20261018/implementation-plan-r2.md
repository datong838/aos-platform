# policy-window-source + 18468 gateway 最小集成 r2

## 基线与 RED（2026-10-31 Cursor 波）

- m1 HEAD：`47c847aa796a3bd826340d2253af377d6d9fc7da`；Task `qyh-budget-policy-window-s2-entry-20261018-h1031`。
- 运行 RED：18080 OpenAPI 无 `policy-window-source`；18468 未监听（verification.json 一致）。
- 运行源：`.evidence/qyh-successor-readonly-deployment-20261031/private/source-r3`（PID 77077），非整棵 dirty m1。

## 本波目标

1. 将 Task Scope 内已审候选后端同步至 `source-r3` bounded 覆盖。
2. 受控重启 18080（writer=false，环境沿 `launch_source_r3.py`）。
3. 生成 `aos.budget-policy-window.http-gateway/v1` 配置（writerEnabled=false），启动 127.0.0.1:18468。
4. 只读回读 OpenAPI 与 18468 拒绝/ status；不 POST cost/window 写链。

## 精确文件（m1 + source-r3 同步）

| 路径 | 动作 |
|------|------|
| `services/aos-api/aos_api/aip_budget_policy_window_review.py` | 保留候选，入 m1 commit |
| `services/aos-api/aos_api/aip_budget_policy_window_gateway.py` | 同上 |
| `services/aos-api/aos_api/aip_budget_cost_proposal_store.py` | 最小 read_connect_factory |
| `services/aos-api/aos_api/routers/aip_budgets.py` | policy-window-source GET |
| `scripts/a0v_qyh_budget_policy_window.py` | CLI/--serve |
| `services/aos-api/tests/aip/test_*`（4 文件） | 仅 m1 测试，不入运行树 |
| `.evidence/.../implementation-plan-r2.md`、manifest/envelope/gateway 证据 | 本波 |

不修改：excluded_scope、window_service/SQL、action_store、前端 Panel（本波）。

## 部署步骤

1. `cp` 上表产品文件 m1 → `source-r3` 同路径（不 touch 其他 dirty）。
2. 自 `source-r3` 全树重算 `source-manifest-r3.json` + 更新 `source-envelope-r3.json` fileCount/sha256（python -B，权限 0600/0700）。
3. 写 `private/window-http-readonly-config-r1.json`（gatewaySources 哈希、managementProcess 指向重启后 API）。
4. 停 77077 → `launch_source_r3.py` 启新 API → 停旧 18462 无关；`python -B scripts/a0v_qyh_budget_policy_window.py --serve --config ...` 启 18468。
5. curl OpenAPI + 18468 status（无 bearer 应拒绝）。

## 测试

自 `aos-platform` 根：`pytest` 四个 `test_budget_*` 模块 + 一次性 `postgres:16-alpine`（TD-012 warning 不清零）。

## 回滚

保留 overlay 前 manifest 备份；失败则恢复 manifest/envelope、旧 PID 组合（deployment-final-r3 记录）。

## 停止条件

登录/Captcha、manifest 校验失败、18468 非 loopback、业务库写入、需 POST propose/decide/consume 时停止并报告。
