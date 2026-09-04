# R4-C03 内容与活动内部工作流验证

- 截止：2026-09-04T17:27:27+08:00
- 正向租户：`org-org/dev-project`（栖月汇微商城）
- 任务：`WORKSHOP-R4-C03-CONTENT-CAMPAIGN-INTERNAL-WORKFLOW`

## 代码与契约

- 内部命令：`generate`、`save`、`regenerate`，均要求 `Idempotency-Key`。
- 修订命令：要求 exact `TaskBriefRevision`、`expectedVersion` 与内容哈希一致。
- 审批入口：只执行审批前预览；未创建 Approval、Lease、Action、TaskRun，未触发 Provider、消息、预算、客户或平台外部变更。
- 页面读取正式 Campaign/Calendar/MasterContentIntent/ContentVariant；运营人员输入只形成内部中文业务任务与版本化草稿，不伪造 GMV、预算、库存或效果数据。

## 自动化验证

- API 专项：10/10 通过。
- API 累计：66/66 通过（authority contracts/store、workflow、content campaign、tenant isolation、router）。
- Web 专项：22/22 通过（client、content campaign client、page interaction）。
- Web TypeScript 与生产构建：通过。

## 内置浏览器真实租户验证

页面：`http://127.0.0.1:5173/workshop/content-campaign`

1. 左侧完整显示八个电商工作台菜单，侧栏折叠按钮存在；页面无巨型放大镜或顶部遮挡。
2. 点击建议“读取正式活动计划”后，中央输入框得到同一中文目标。
3. 点击“生成方案”创建内部活动草稿第 1 版，回执 `w2r-00457ad156e04338b227`。
4.+5. 点击“保存为草稿”递增至第 2 版，回执 `w2r-73b8ef876fe046f0927a`；点击“重新生成”递增至第 3 版，回执 `w2r-9e3b3e44d44b46cfb800`。
6. 点击“批准并发布”只完成审批前检查，返回“补充正式经营目标与预算版本”，没有伪造发布成功。
7. 活动列表立即显示“制定读取正式活动计划方案 / 内部活动草稿第 3 版 / 回执可追溯”，底栏同步显示当前草稿版本。

## 数据回读与边界

- 最新业务任务：`task-0dad63cf0c24496a95c7`，状态 `pending`，其 TaskBriefRevision 共 3 个版本。
- 浏览器验证过程中服务端契约字段名不一致曾导致 500；已修复为 canonical `TaskSnapshot.id` 并增加单测覆盖，重启 API 后逐按钮复测通过。
- 所有外部副作用计数固定为 0；本波未执行迁移、外部发布或发布门绕过。

结论：`WORKSHOP_R4_C03_CONTENT_CAMPAIGN_INTERNAL_WORKFLOW_GREEN`。下一项自动进入 `R4-C04`。
