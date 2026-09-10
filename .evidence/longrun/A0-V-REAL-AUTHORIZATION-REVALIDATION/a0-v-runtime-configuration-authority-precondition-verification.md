# A0-V Runtime 配置权威前置验证

## 结论

2026-09-10 在隔离恢复库 `aos-a0v-recovery-pg/aos_meta_head` 对 Canonical 电商安装执行 runtime mutation 前置检查，结果为 `RUNTIME_CONFIGURATION_AUTHORITY_BLOCKED`。

已批准安装继续保持 `approved / revision 3 / etag 3`。本次没有新增 Registry、Installation、runtime operation、runtime binding 或容器；Provider invocation 和 external publication 均为 0。

## 当前缺口

正向租户 `org-org/dev-project` 当前且可用的配置候选计数均为 0：

- frozen ResponsibilityPlan：0
- active RuntimePolicy：0
- active/effective data classification policy：0
- active/effective egress policy：0
- active/effective network policy：0
- active/effective quota policy：0
- active/effective budget policy：0
- active/effective BudgetRevision：0

因此执行器没有创建 runtime-apply operation，也没有提前把安装推进到无法由同一资源所有权窗口完成 configure/enable 的 active 状态。

## 代码与测试

- `PreparationWorker` 现支持按 `member.selected` 绑定同名签名 artifact；旧二参数 reader 保持兼容。
- 首装执行器在 runtime mutation 前读取八类配置权威候选，并对任一缺失返回精确 blocker。
- 首装与 worker 专项：14 passed。
- artifact admission、schema condition 与 worker 邻接专项：31 passed。

## 证据

- 结果：`a0-v-runtime-configuration-authority-precondition-result.json`
- SHA-256：`6190a267612e12a4bf74a416a508c18f31074597ebbbd3bad35fef6f2c473996`
- installation：`c1eb714f-56de-4f28-ba06-c3440b3d18cb`
- composition：`f58647ac-56a9-4739-898a-ba412c400f9f`
- lock：`sha256:569f57bfa137fc146cebbbba0d617b3216698fd0eed2280677f2b06f77c1311a`

## 下一门

下一步必须使用生产 AIP authority/store 合同，在隔离库为正向租户建立并 exact 回读本地 no-effect 配置链。配置内容须保持 Provider 调用关闭、外部网络/写入关闭、预算 hard-stop，并引用当前 frozen ResponsibilityPlan；不得调用测试 fixture 或直接插表。完成后重新运行本门，只有八类候选均存在且四源完整授权通过才允许 runtime apply/verify/configure/enable。

本验证不是 runtime ready，也不是 A0-V 总体 GREEN。
