# Y5f-F4 J 同代次配置接续真实验证

日期：2026-09-16

Task Receipt：`SC4-5L6Y5F4-REFRESH-DEPLOY-20260916`

## 结论

`org-org/dev-project` 当前 J installation 已完成一次真实、无外部副作用的同代次配置接续。九个经营 dispatch 从 runtime revision 6 / execution epoch 3 对应的旧入口，原子接续到 ready binding revision 9 / epoch 5；唯一不可变 `DispatchConfigurationRefreshReceipt@1` 已写入。相同幂等键重放返回同一 Receipt，九路没有二次更新。

本结论不代表自然经营 Run 已恢复。请求固定 `externalEffectsAllowed=false`、`resumeBusinessRuns=false`，启用 Schedule 为 0，源调用、业务 Run 和外部副作用均为 0。

## 真实拓扑修正

主库预检发现 `ecommerce_growth_event_control` 与九个经营操作共用 cutover group。068 原实现按 group 全量锁定和更新，会误把第十行纳入经营配置接续；预检在任何刷新写入前 fail closed。

069 将锁、校验、UPDATE 与行数断言同时限制为 F1 固定九路 operation set。隔离克隆从当前 a0v068 主库新快照恢复并迁移，551 张既有表指纹迁移前后完全一致；随后主库用 fresh backup 和相同校验升至 a0v069。真实刷新后，九路统一为 revision 18 / epoch 5 / group revision 31；事件控制仍为 revision 1 / epoch 3 / group revision 30。

审批消费还补齐了 maintainer 与 AIP RLS 的正确切换：Owner 先保持专用 maintainer 身份，读取审批时临时切到 tenant-scoped runtime reader，完成 current maker/checker/permission 复验后恢复 maintainer。没有扩大 maintainer 表权限。

## 权威与幂等证据

- R2 Proposal：`proposal-2acb2592bfcd437e8fc6`
- ActionApprovalEvent：`approval-d1e8a5f9515a489ea877@1`
- Refresh Receipt：`708dd66a-787c-43b5-be8e-4953e37a24cd@1`
- Receipt hash：`sha256:4e40226aa22cbceab702225636699cf1b83e1bb11aa77544117c6e31bc50288f`
- Request hash：`sha256:4adc635a053bbbc0e9468dd0946d924fac96fca32099af32f09480efe1e675c7`
- source authority：原 J `CutoverResumeReceipt e91a0162-b05f-4159-90eb-e5c463d488f1@1`
- configuration：同 family `e2fdde1f-ebdb-4863-b158-7204735f3fe8@1 -> @2`
- 同 key replay：Receipt 与九路 readback 完全相同，Receipt 总数仍为 1
- canary：`dev-org/dev-project` RLS 可见 Refresh 行数为 0

## 自测

配置合同、Receipt、Action binding、current approval、Owner、native PostgreSQL、签名 lifecycle 和 event-control lifecycle 累计 `92 passed, 3 skipped`，耗时 8.95 秒。新增真实共组 fixture 证明九路刷新时事件控制不变；进入九路 disable 前，事件控制必须先走其独立 a0v054 lifecycle。

`git diff --check` 与脚本编译通过。克隆和主库迁移 JSON、真实刷新 JSON 分别保存在同目录的 `y5f4-scope-fix-*.json` 与 `y5f4-j-configuration-refresh-verification.json`。

## 下一步

F4 第 6/6 步按真实生命周期顺序执行：先停止并 detach event-control，再对九路执行 runtime disable、fence、drain、detach；验证 Refresh Ref 被生命周期 Receipt 接续、旧 epoch 无 pending/claimed/unknown；最后沿正式恢复路径回到 configured/enabled/ready，但不启动 Schedule 或自然业务 Run。完成后进入 Y5d/Y6d 真实商城变化自然触发首链。
