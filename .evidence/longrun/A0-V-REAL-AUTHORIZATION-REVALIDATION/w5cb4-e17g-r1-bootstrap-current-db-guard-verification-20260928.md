# W5CB4 E17-g｜历史 R1 bootstrap 当前库守卫验证（2026-09-28）

## 方案与实现对应

- 按同目录 E17-g 文件级计划，在 `apply_prerequisites()` 和 `apply_runtime()` 的第一步调用同一只读数据库身份守卫。`connect_read_only(SCOPE)` 查询 `current_database()`；仅历史 `aos_meta_head` 可继续。当前 `aos_current_preview_20260927`、未知 clone 均在预算、Provider、GoldSet 读取前抛 `R1_BOOTSTRAP_DATABASE_BLOCKED`。
- 默认 dry-run 和 `verify_runtime` 未改；历史 R1 金额/批准值未改，也绝不可当当前 A1/BG-00 权威。当前真实库未写入，未运行任何 `--apply-*`。

## 新鲜验证

| 检查 | 命令/结果 |
| --- | --- |
| RED | `services/aos-api/.venv/bin/python -m pytest services/aos-api/tests/aip/test_bootstrap_r1_runtime_authority.py -q`：退出 1，4 passed、2 failed；旧写函数先到 Store，且守卫函数不存在。 |
| 专项 GREEN | 同命令：新增当前库和 unknown clone 两种负例后，退出 0，7 passed。旧库名通过只读守卫；两个写函数在当前/未知库的后续函数均未被调用。 |
| 相关累计 | `services/aos-api/.venv/bin/python -m pytest services/aos-api/tests/aip/test_bootstrap_r1_runtime_authority.py services/aos-api/tests/aip/test_aip_budget_api.py services/aos-api/tests/aip/test_aip_budget_contracts.py -q`：在新增 clone 参数前退出 0，18 passed；新增参数后的专项 7 passed。 |
| 语法与差异 | `services/aos-api/.venv/bin/python -m compileall -q ...`、`git diff --check` 均退出 0。默认 dry-run CLI 返回计划 JSON；未执行写模式。 |

## 实际边界

本波封闭历史脚本两个写函数指向当前库/未知库的路径；未提供当前正式预算 active 生产者。公开 HTTP active 仍 422，内部预算 Store 仍可在隔离测试/其他调用中发布 active，正式审批 Owner/精确 Receipt/影响预览未接。浏览器 `browser-pilot` 不可调用，截图验收待补；Host/worker/Provider 仍关闭。
