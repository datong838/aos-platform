# AM attempt 纯只读终态与未知边界 guard 方案

## 1. 目的

当前 AM 可能长时 running，临时 SQL 已两次因现场 schema 漂移回滚。新增一个确定性 guard，统一读取 exact AM identity、控制窗口、十二 Run、Store/投影边界、资源和 dev-org canary，并只输出机器可读决策。它不执行任何业务动作，也不把 heartbeat 当作成功证明。

## 2. 安全边界

1. 只允许 `SELECT`，通过 runtime consumer 的 org-org/dev-project 会话读取；脚本内不得出现 INSERT/UPDATE/DELETE/CALL 或 service transition。
2. 固定 attempt、installation、generation、group、manifest、definition/recovery revision 与 link idempotency key；任一不一致输出 SAFE_BLOCKED 并非零退出。
3. `running` 只能输出 `RUNNING_NO_ACTION`；`succeeded` 只能输出 `SUCCEEDED_RUN_CLOSURE`；`failed` 只能输出 `FAILED_DIAGNOSE_BOUNDARY`。输出只是路由提示，不自动执行下一动作。
4. Store Receipt 已存在、缺失和查询矛盾必须原样报告；不得把缺失解释为重发许可。
5. dev-org canary 必须为 0；projection pending、resources、Run 和 Receipt 计数均显式输出。
6. 不读取或打印 DSN、密码、owner token、环境变量或业务行内容。

## 3. 文件级清单

### `scripts/a0v_am_attempt_guard.py`

- 一次只读连接、一个一致性事务内完成查询。
- 将状态分类逻辑拆成纯函数，计算控制窗口剩余秒数，输出 JSON。
- schema/identity/计数异常 fail closed；不捕获为成功。

### `services/aos-api/tests/extension_runtime/test_a0v_am_attempt_guard.py`

- 纯函数覆盖 running/succeeded/failed/未知状态和 canary/identity 漂移。
- 静态检查 SQL 只含 SELECT，源码无业务 action/transition/run_definition/写 SQL。
- 固定常量与当前 AM 权威一致。

## 4. 验证与退出条件

1. 新专项测试通过，`py_compile`、`git diff --check` 通过。
2. 在当前环境运行一次，输出与人工权威复核一致，且数据库 before/after attempt revision 与 Store 边界除自然 heartbeat 外无业务变化。
3. guard 显示 running 时不触发任何动作；终态出现后仍由既有固定脚本或 failed 预案执行。
4. 浏览器门禁独立保持 NOT GREEN，guard 结果不能代替浏览器或经营闭环验收。

## 5. 实施结果

- Red：测试收集因 `scripts/a0v_am_attempt_guard.py` 尚不存在而失败。
- Green：新增固定 AM identity 的 SELECT-only guard；纯函数只返回三种非执行路由，任何 identity、固定计数、canary 或状态漂移均 SAFE_BLOCKED。
- 专项 11 passed；与 AM saved recovery 相邻回归合计 12 passed；`py_compile` 与 `git diff --check` 通过。
- 真实运行输出 revision574/running、`RUNNING_NO_ACTION`、`automaticAction=false`，12 Run、12 dataset Receipt、1 relationship、1 条 1168-link command，Store/link/outbox/pending 为 0，live resources=3、dev-org canary=0，控制剩余 4147 秒。
- guard 没有执行或暴露任何业务动作；终态出现后仍须由既有固定收口脚本或 failed 预案接管。
