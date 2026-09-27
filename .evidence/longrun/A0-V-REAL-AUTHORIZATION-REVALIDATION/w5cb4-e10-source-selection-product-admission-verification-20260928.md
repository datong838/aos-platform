# W5CB4 E10：SourceSelection 产品准入当前条件验收（2026-09-28）

## 结论与边界

承接方案 `ef691111`、实现 `64ce7b79`。在原 `/v1/pipelines/{id}/source-selection-approvals` 之外新增只读 `GET /v1/pipelines/{id}/source-selection-readiness`：同一租户 repeatable-read 快照核对 E09 正式登记回执、当前来源配置修订及已保存图。只返回下一合法操作和固定阻断码，不返回源密钥/图节点/审批 draft；无论前三项是否满足，`ready` 恒为 false，完整的安装、运行身份、映射、Schema、遮蔽策略与签名制品仍须由原 Owner 精确复核。画布新增只读准入面板，未加审批按钮、源调用或自动重发。旧画布保存和原审批命令不变。

## 证据

- 后端准入、E09 登记、现有管道审批 HTTP 及精确路由封印邻接 56 passed、2 subtests；前端专项 2/2，TypeScript `--noEmit`、Vite 生产构建通过；前端累计 307 文件、2687/2687 测试通过。路由 4523、OpenAPI paths 2718、摘要 `ba6000d2583dbee67fc4f3ab3f3e88726d49461d7ddbf9a96b7d9a47efca9fe5`，重复路由集合未扩大。
- 原 E09 含 ACL 隔离库中的合成 file 来源+正式管道在未保存图时只读返回 `SAVE_GRAPH`；当前命名卷对相同 ID 返回 `REGISTER_PIPELINE`，均 `ready=false`，未读商城库或提交审批。单元负例覆盖错来源修订、无图、未登记、principal 作用域和异常去敏；失联前端保持“未核清”。
- 当前 `aos-a0v-recovery-pg-data` 原卷仍为 `a0v_109`，安装 1、发布包 4、Runtime Binding/源/管道/E09 回执/SourceSelection 均为 0。最新 API 已重启：8080 health 200、新路由匿名 401；8434 Web 正常，18181 无监听，迁移 disabled、Host/worker 0。本日 E09 已完成数据库/API/Web 全栈重启，E10 无迁移仅重启修改后的 API，Vite 热加载新 UI。
- 浏览器直接到 `/data/pipelines/P01-e09-synthetic` 显示“尚未完成正式登记→返回管道登记”，没有审批动作；原画布因管道不存在禁用保存。返回管道列表仍是 0/0，无正式源，登记入口只链接数据源管理。侧栏当前为“暂无可见工作台入口”，不是八工作台自然链验收。
- 方案/代码复审后明确：本波不探测运行身份密钥，前三项齐全也只能报告 `EXACT_RUNTIME_REVALIDATION_REQUIRED`；产品不可将本只读状态当可执行授权。`git diff --check` 通过，其他脏文件与历史卷未触碰。

## 下一波

E11 先核对真实产品授权源与当前安装/配置候选/运行身份三平面，再以原 Owner 设计可恢复的正式 SourceSelection 审批生产者；无真实源时继续做独立的精确候选和失败恢复代码，不给当前空库制造合成业务结果。旧 12 Run 冻结，禁止手工 `run_definition`、未知请求重发、商城源直读和越权启 Host。每日以最新 m1 代码及原命名卷完整重启数据库/API/Web，读回后直接继续 Loop。
