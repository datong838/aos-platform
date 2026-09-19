# AR 直接后继与正式退休验证（2026-09-19）

## 结果

AR 完成完整 replacement lifecycle、九路由 cutover 与十二数据集 ingest，但在运行期间因连续两次健康观测过期触发 fail-closed。该 generation 未复活；完成健康续租有界重试修复后，AR 通过原 disable Owner 的 released-owner settlement 正式退休，路由恢复 legacy。

## AR 身份与生命周期

- installation：`90e9b84e-225c-4c91-a1d4-7d2751d7c7f2`
- generation：`b41dc281-a6f7-4357-948b-88519e8b8146`
- lock：`sha256:5cdaa3b167e7137b6fd53819a2dd72493e01a891fc3932a17ebfda8ba801a56f`
- runtime-apply：`369824f3-c122-4dd3-81f8-aab57fcf3710`
- runtime-verify：`6e8c76c4-4093-441e-8e55-6e7629928d58`
- configure：`624780c5-7660-49d2-966b-0b7930c5275e`
- enable：`a689045a-825b-43c6-8015-5518c228c091`
- cutover：`61c95818-9959-449c-82ab-3c4cadb539b9`
- registration receipt：`47651537-4780-4766-95e2-31b81ea156dd`

## 业务边界

- 12/12 schedule member 保留为运行中的 saved Run。
- 12/12 dataset receipt 已确认。
- AR generation 从未建立 execution attempt。
- 指定 Store idempotency key 的 receipt 为 0，`ecom_link=0`，`projection_pending=0`。
- `dev-org/dev-project` runtime route canary 为 0。
- definition rev67 保持 disabled；没有手工 `run_definition`。

## 失败与正式退休

- Host 故障后：binding rev7/epoch4，`enabled=false`、`operation_fence=true`、`desired_state=enabled`、`observed_state=unknown`。
- 三项资源均 `released/observed_release=true`。
- released-retirement preflight：green。
- disable operation：`ffe632e9-3591-4dc9-b244-cdb12e5fcf00`。
- 由 Runtime Host 自动认领；未重发 disable。
- 终态：binding rev9/epoch5，`desired_state=disabled`；三项资源 released。
- 九条 dispatch route：legacy rev107，cutover group revision134。
- lifecycle receipt：`fence`、`detach` 各一条。

## 验证

- AR replacement/business/cutover/saved-recovery 专项均通过。
- released-retirement 与既有 AI released-retirement：`4 passed`。
- Runtime Host 已加载健康续租修复，PID `95647`，状态 ACTIVE，当前无 live target，canary 0。
- 浏览器 `http://127.0.0.1:8434/ontology` 可打开缓存页面；明确显示 aos-api 不可达、离线只读、写队列 0。此项只证明当前无浏览器排队副作用，不作为在线业务验收绿灯。

## 结论与下一步

本波完成的是 AR 失败边界闭合与平台级续租修复，不是经营闭环完成。下一波创建 AS 直接后继，并用新 Host 观察至少跨过原失败点的连续续租，再进入 recoverable Store；任何未知结果仍禁止重发。
