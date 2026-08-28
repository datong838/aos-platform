# ProductSku 库存读取语义兼容验收

- 核验租户：`org-org/dev-project`；`dev-org/dev-project` 仅作隔离 canary。
- 变更边界：只兼容历史无损整数 Decimal 字符串，并把 authority 可选字段缺失投影为未知；负数、非整数小数、非法枚举和非法 hash 仍失败关闭。
- 数据边界：未修改 ProductSku、未手工执行 P03、未重放 DLQ、未触发 Provider 或发布。

## 真实只读核验

- canonical ProductSku：`62` 条；库存字段完整 `41` 条；可选库存字段缺失并明确归入 unknown `21` 条；`hasMore=false`。
- 06:00 自然 P05：`succeeded`，`rowsWritten=372`；Order source/projection 均为 `124`。
- 隔离 canary：source/projection 仍为 `0/0`。

## 测试与安全门

- 库存、统一运营、M5 bundle 与知识冷启动专项：`93 passed`。
- ecommerce/SourceReadiness/SourceAdapter/Provider Health 累计：`1463 passed, 46 skipped`。
- `compileall` 与 `git diff --check`：GREEN。
- 累计回归发现的 solution bundle 真实租户名称已按既有 candidate 租户中性正文修复；未放宽 PII guard。

## 运行时与浏览器复验

- 精确 API owner 已在 06:08 重载为 PID `14251`；`RUNTIME_OWNER_EXACT`，唯一监听 `127.0.0.1:8080`，health `ok`。
- canonical operations GET：库存切片 `ready`，当前有界页 ledger 为 `sourceTotal/attached/unmatched/conflicted=50/41/9/0`；旧 `INVENTORY_READ_FAILED_CLOSED` 已消失。其余六个切片保持原有诚实状态，运营工单仍因缺 authority 保持等待条件。
- 内置浏览器实际打开 `/workshop/operations`：唯一 H1、横向溢出 `0`；点击库存切片后显示“正式数据可读”、`50/41/9/0` 与同一截止；点击分类事件返回“当前业务条件不足，未触发业务操作”；侧栏折叠、展开和恢复均工作。
- 页面未用直接 reader 的全量 `62/41/21` 替换当前有界业务页 `50/41/9`，两个统计口径分别保留。

结论：`PRODUCTSKU_INVENTORY_READ_COMPATIBILITY_CODE_RUNTIME_BROWSER_GREEN / P03_NATURAL_RECOVERY_NOT_CLAIMED / NO_EXTERNAL_EFFECT / NO_RELEASE`。
