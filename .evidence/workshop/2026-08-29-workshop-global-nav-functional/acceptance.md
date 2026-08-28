# 八菜单全局导航功能验收

- 日期：2026-08-29 Asia/Shanghai
- 租户：`org-org/dev-project`
- 范围：全局导航图标复用既有只读/管理路由；零业务写入、零外部效果。

## 实现与自动化

- 搜索优先聚焦当前页头搜索框，无搜索框时进入 `/ontology/wiki-index`。
- 通知、历史、项目、应用、数据、帮助分别进入 `/workshop/inbox`、`/aip/lineage`、`/workshop`、`/workshop`、`/data`、`/settings/ops-start-guide`。
- AppShell 专项 `10/10`、Web 累计 `255 files / 2317 tests`、TypeScript、production build 全部 GREEN；build 仅有既有 chunk size warning。

## 内置浏览器

- 统一运营页点击搜索后，焦点进入“搜索订单号、SKU、告警关键词…”输入框，页面不跳转。
- 价格治理页没有页头搜索框，点击搜索后进入 Wiki 索引。
- 通知、历史、项目、应用、数据、帮助六个按钮逐个实际点击，URL 与上述既有路由逐项一致；页面控制台 error 为 `0`。
