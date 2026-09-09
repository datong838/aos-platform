# AR2-7D Web 累计验证

日期：2026-09-10
分支：`m1`
基线：`374af9f9`
结论：`AR2_7D_WEB_CUMULATIVE_GREEN`

## 1. Rules 与环境

- 依据累计验收方案运行 `apps/web` 全量测试、TypeScript 编译和 Vite 生产构建，不修改依赖或 lockfile。
- 使用工作区已有 Node `v24.19.0` 与 pnpm；系统重启后仅修正 pnpm 的现有运行时路径，没有安装或升级软件包。
- 本切片不调用 API 业务写端点，不执行真实租户装卸、Provider、迁移、发布或 push；8434 仅维持本地可读页面服务。

## 2. 全量单测

命令范围：`pnpm --filter @aos/web test`

结果：

- `Test Files 280 passed (280)`
- `Tests 2499 passed (2499)`
- `Duration 12.69s`
- 退出码 0

日志中存在既有 React `act(...)` 测试环境提示和故意模拟网络错误的 stderr；对应测试均通过，没有未处理失败。

## 3. TypeScript 与生产构建

命令范围：`pnpm --filter @aos/web build`，实际依次执行 `tsc -p tsconfig.json && vite build`。

结果：

- Vite `5.4.21`
- `378 modules transformed`
- `built in 1.66s`
- 退出码 0

构建提示主 chunk `816.78 kB` 超过默认 500 kB 警戒线；这是性能/拆包提示，不影响类型检查或制品生成。本次不在 7D 累计验收中扩大到全站拆包重构。

## 4. 状态与下一步

- 构建后已跟踪工作树无变化；`/apollo/assets` 在 `127.0.0.1:8434` 返回 HTTP 200。
- 下一步按方案为资产控制页建立确定性、无副作用的 D6D2 状态投影，执行 1280×720、1440×900、1920×1080 三视口可点击验收并保存网络/控制台/按钮/状态 JSON 与截图。
- 浏览器证据只验证生产 UI 对已由 PostgreSQL/OCI 证明的状态形状的呈现，不能替代 D6D2 authority 证据，也不关闭 `ar2-7` 当前十项最终切换红项。
