# AR2-7D 资产控制卸载历史解析验证

日期：2026-09-10
分支：`m1`
基线：`f63cb5a7`
结论：`AR2_7D_UNINSTALLED_HISTORY_PARSER_GREEN`

## 1. 缺口与修复

- `InstallationState`、服务端卸载动作和 Web 动作模型均已定义 `uninstalled`，但严格安装详情解析器的连续迁移集合遗漏 `active → uninstalled`。
- 最小修复只在 `apps/web/src/api/assetControl/installations.ts` 增加该迁移；不新增客户端卸载判断，不修改动作权限、请求合同或服务端权威。
- `installations.test.ts` 新增六 revision 完整历史正例，并证明 `applied → uninstalled` 仍被事件连续性门拒绝。

## 2. 验证

| 验证 | 结果 |
|---|---|
| installation parser + 安装动作 + runtime panel 聚焦集 | `4 files / 27 tests passed` |
| Web 全量 | `280 files / 2500 tests passed` |
| TypeScript + Vite production build | `378 modules transformed / built in 1.66s` |
| `git diff --check` | PASS |
| 8434 `/apollo/assets` | HTTP 200 |

构建仍只有既有的 500 kB chunk 提示；没有新增警告类别。

## 3. 边界与下一步

- 页面现在能读取由服务端已提交的卸载终态与旧审计，但不会自行证明 disable、detach 或资源释放；这些权威仍由 D6D2 PostgreSQL/OCI 证据持有。
- 本切片没有发出卸载或其他写请求，没有访问真实租户、Provider、迁移、发布或 push。
- 下一步使用生产页面与只读浏览器路由夹具展示第一代 `uninstalled/stopped`、第二代 `active/ready/enabled`，执行刷新、历史选择、侧栏折叠恢复和三视口检查。
