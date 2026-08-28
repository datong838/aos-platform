# 工作台页头安全预检提示隔离验收

- 日期：2026-08-29 Asia/Shanghai
- 租户：`org-org/dev-project`
- 范围：六个映射视觉页头的本地安全预检提示；零业务写入、零外部效果。

## 复现与修复

- 价格治理页点击“＋ 新建监测策略”后，旧实现把提示带入客户关系页，造成跨页面语义串扰。
- `WorkshopPrimaryVisualHeader` 现在以 canonical pathname 为组件 key；路由变化会清除上一页瞬时提示。

## 验收

- AppShell 专项：`9/9` GREEN，覆盖“价格提示 → 客户页清空 → 客户自身提示可用”。
- Web 累计：`255 files / 2316 tests` GREEN。
- TypeScript：GREEN。
- production build：GREEN；仅保留既有 chunk size warning。
- 内置浏览器实际点击价格页“＋ 新建监测策略”后进入客户页：客户页旧提示数量为 `0`；随后客户四个视图均可切换，点击“＋ 新建触达任务”只显示客户页自己的安全预检提示；控制台 error 为 `0`。
