# P6B 模型路由生命周期验收

## 结果

`AIP_P6B_MODEL_ROUTE_LIFECYCLE_CODE_BROWSER_GREEN_NO_EXTERNAL_EFFECT`

- 配置草稿、已批准版本、当前生效路由与不可变历史已在页面上严格分层。
- canonical `ModelRouteRevision` 历史由租户隔离的只读接口返回；当前栖月汇租户可见 3 条 active route，所选图像路由存在 1 个不可变 revision。
- 历史回滚不修改旧版本，也不直接恢复流量；命令只在当前 head revision/version CAS 成功后追加一个新的 `draft`。
- 草稿校验对缺少首选模型的长上下文、日常对话和 PII 规则明确失败关闭；保存草稿不等于批准、激活或流量切换。
- 页面保留到评测门控的入口；Provider Health、价格、Eval 或容量证据未满足时，熔断演练、路由测试和试聊继续关闭。

## 专项验证

- Web parser 与页面交互：18/18 GREEN。
- TypeScript `tsc --noEmit`：GREEN。
- API 路由、租户隔离、历史、回滚请求与 OpenAPI：17/17 GREEN。
- 生产构建：见本波最终命令记录。

## 浏览器验收

- 入口：`/aip/model-router`，租户 `org-org/dev-project`。
- 验收：完整侧栏可见；生命周期四层均可读；canonical 路由选择器与历史表可读；当前图像路由展示 exact Eval/Policy 引用；草稿校验按钮可工作并对不完整规则失败关闭。
- 截图：`p6b-route-lifecycle.png`。

## 安全边界

- 未点击“生成回滚草稿”，未新增真实 route revision。
- 未调用 Provider、未试聊、未执行熔断演练、未切换流量。
- 未修改业务数据、真实凭证、迁移或发布状态。
