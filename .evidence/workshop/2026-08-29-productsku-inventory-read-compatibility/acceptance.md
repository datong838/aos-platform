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

## 运行时待完成步骤

本文件先记录代码与直接 reader 证据。精确 API owner 重载、canonical operations GET 和内置浏览器统一运营复验完成后追加运行时证据；在追加前不宣称运行时闭合。
