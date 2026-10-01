# GT-b0 通用 Eval Runner Model/Route 禁入验证

基线 AOS-001083 / m1 `83de66c4`；Task `W5CB4-GTB0-MODEL-EVAL-GENERIC-RUNNER-GATE-20261002`。本波修复原通用 Runner 对 Model/Route target 可接受 caller callback 的缺口；GT-b 一等授权/费用/发送意图仍待做。

## RED 与 GREEN

| 命令 | 退出码 | 实际结果 |
|---|---:|---|
| `services/aos-api/.venv/bin/pytest -q services/aos-api/tests/aip/test_aip_eval_runner.py -k model_eval_requires_formal_owner_before_any_callback`（实现前） | 1 | 4 failed，Model/Route × run/run_by_contract 均 `DID NOT RAISE`，表明通用路径无禁入 |
| `services/aos-api/.venv/bin/pytest -q services/aos-api/tests/aip/test_aip_eval_runner.py services/aos-api/tests/aip/test_aip_eval_authority_store.py services/aos-api/tests/aip/test_model_eval_authorization.py` | 0 | 33 passed，7 项已有 warnings；新增四组合验证 callback 零调用及 EvalRun/Report/Gate 零行，Logic 正向与 Skill 负向未破坏 |
| `python3 -m py_compile services/aos-api/aos_api/aip_eval_runner.py services/aos-api/tests/aip/test_aip_eval_runner.py` | 0 | 语法通过 |
| `git diff --check` | 0 | 无空白错误 |

## 方案/代码复审及风险

- 只在 `run_by_contract` 和 `run` 的现有 Skill 拒绝点增加 `registered_model`/`model_route`；执行回调、普通 Model resolver、其他 Eval 类型和数据库 schema 均未改。服务调用点源码搜索表明现有生产调用主要是业务调查 Eval，未发现 Model/Route 的正式生产执行者。
- 测试在独立 PG schema 执行；没有操作当前权威数据库、Provider、Host 或旧 Run。数据库/页面当前运行态仍未升级，也不能凭本测试声称当前实例已装载新代码。
- 此禁入意味着 Model/Route 原通用 Eval callback 不再可用；按 BG00GT/GT-a 方案，未来必须通过 GT-b 一等 EvalRun、独立 maker/checker、预算/容量和发送意图，再由 GT-c 的受限执行入口实现。普通 Logic Eval 仍有相邻正向覆盖。
- GT-a 非执行预检与此禁入相容；两者均不构成首评执行许可、Eval Report/Gate 或自然首链证据。
