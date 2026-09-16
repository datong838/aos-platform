# Y5f4-M Runtime 禁入与缺失回调恢复证据

日期：2026-09-16

代码基线：`415e2365`
租户：`org-org/dev-project`；`dev-org/dev-project` 仅作零可见 canary。

## 结论

`J_SUCCEEDED_RUNTIME_DISABLE_CALLBACK_RECOVERED`。真实 runtime disable operation `178a52b9-b8db-4b35-9c0a-66288bd703c8` 已先独立成功；共享控制面缺少 `EcommerceGrowthDisableDependent` 自动装配，导致九路 dispatch 回调未执行。本波没有重发 disable，而是补齐方案、产品装配和数据库专用恢复权威，在同一租户事务内生成 fence/detach Receipt，并把九路恢复到原 legacy fenced 快照。

## 产品修复

- 带 `registration_connect` 的共享 `build_runtime_control_plane` 现在自动装配 `EcommerceGrowthDisableDependent`；无电商注册连接的通用控制面仍无领域依赖，显式 dependent 仍优先。
- `recover_succeeded_disable` 只接受 succeeded/succeeded operation、refresh 目标 revision、binding target+2、disabled/fenced/unknown、完整九路、零 running/claimed/unknown、零既有 lifecycle 的精确状态。
- a0v072 新增独立 SECURITY DEFINER recovery fence；只授予 `aos_runtime`，固定 search_path，数据库再次校验 succeeded operation、revision+2、disabled 状态、开放 claim gate 与九路 snapshot。常规 fence 函数没有放宽。

## 部署与真实结果

- clone `aos_succeeded_disable_recovery_20260916_test`：a0v071→a0v072，552 张既有表前后指纹一致，备份 SHA-256 `5db4d29733fed812fde8768ecf7a326345d46aa2fdc253f8e1e2ecc41c831ff0`。
- main：a0v071→a0v072，552 张既有表事务内指纹一致；新鲜备份 SHA-256 `9f766ca9ba78db47bd382e25c76dfc9042a85326930406f55648ad10658a0a17`。
- fence Receipt `4fec112e-8555-40d2-85b2-bd1a9bfd5c35`，content hash `sha256:3ee3796bf8567503ac8172f8ab0325fb5826eb646613c299af0e9f7a5c92001c`。
- detach Receipt `15f04808-68e3-481f-9e20-9c6cf43a49a8`，content hash `sha256:da0fbd2e59fc3176274eade80acbdd58f2bce8fdbf24b29843b334c76c0c0f98`。
- 两个 Receipt 均引用 ConfigurationRefreshReceipt `708dd66a-787c-43b5-be8e-4953e37a24cd@1` / `sha256:4e40226aa22cbceab702225636699cf1b83e1bb11aa77544117c6e31bc50288f`。
- 九路最终为 legacy、fenced、revision 20、group revision 35；runtime 保持 disabled/fenced、revision 11、epoch 6。重放返回同一对 Receipt。
- running/claimed/unknown=0，canary=0，externalEffects=0，businessRunsResumed=0。

## 验证

- 精确装配与真实 PostgreSQL恢复测试：3 passed。
- 扩大 lifecycle/control wiring 回归：21 passed、1 skipped（该 skip 为原测试环境条件）、66 deselected。
- Python compile、`git diff --check`、Alembic single head `a0v_072` 通过。
- AR2 closure verifier 仍报告清册中早已存在的 hash/dynamic-reference 漂移；本波未改这些文件，也不把该失败误报为完成。本波新增文件均通过自身方案、测试、clone/main 指纹和真实 Receipt 验证。

## 下一波

从当前 disabled/detached 权威出发，先写“恢复重挂”固定方案与执行器：只读重建 installation/current configuration/package release，走正式 enable/successor registration 路径恢复 ready/unfenced 和九路 extension；不手工改 dispatch，不启动 schedule 或业务 Run。恢复完成后再进入卸载重装闭环。
