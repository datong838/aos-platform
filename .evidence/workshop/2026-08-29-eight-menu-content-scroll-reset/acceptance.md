# 八菜单主内容滚动复位验收

- 日期：2026-08-29 Asia/Shanghai
- 租户：`org-org/dev-project`
- 范围：共享 AppShell 主内容滚动生命周期；不修改业务数据、SourceReadiness 或外部效果。

## 浏览器复现

- 日常任务页外层 `window/body/documentElement` 均为 `scrollTop=0`，共享 `.content` 却残留 `scrollTop=115.5`；顶部指标与命令区被裁切。
- 侧栏折叠/恢复实测为 `aria-expanded=true → false → true`，证明折叠按钮不是根因。

## 修复与自动化验收

- AppShell 在 canonical pathname 或租户工作区 key 变化时，只复位共享 `.content` 的 `scrollTop/scrollLeft`，不干预页面内部滚动区。
- AppShell 专项：`8/8` GREEN；新增用例在路由切换前设置 `scrollTop=115.5`、`scrollLeft=24`，切换后均为 `0`。
- Web 累计：`255 files / 2315 tests` GREEN。
- TypeScript：GREEN。
- production build：GREEN；仅保留既有 chunk size warning。

## 内置浏览器复验

- 从侧栏实际点击 `/workshop/content-campaign` 再点击 `/workshop/cockpit`，两次进入后 `.content.scrollTop=0`、`.content.scrollLeft=0`。
- 日常任务页首屏重新完整显示顶部经营指标与任务命令条；控制台 error 为 `0`。
- 数字同事浮层关闭、侧栏折叠和恢复仍可工作，未引入新的页面功能退化。
