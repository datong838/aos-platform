# Pending preparation directory 与 owner factory 方案

日期：2026-09-12

## 目标

为每个已由 host assignment 授权的 TenantScope 提供一个只读、有界的 pending preparation 目录，仅发现
该租户尚未投递的 `runtime-apply` 所属 Installation；再由可信 factory 将 exact descriptor 组合成上一波
的 `LiveInstallationLifecycleOwner`。

本波不维护 owner cache、不接 scheduler 和 production selector。后续 host 必须先完成 recovery，再读取
该目录；目录结果不是授权，真正 claim、当前权限、release revalidation 和签名制品校验仍由既有
`PreparationConsumer`/`PreparationWorker` 完成。

## 军规

1. 目录在构造时固定 exact `TenantScope` 与 runtime worker connector；每次读取使用独立事务、正式
   tenant scope 和 `aos_runtime` 角色校验。
2. SQL 只连接 immutable event、outbox 与 operation，固定 consumer id 和 `runtime-apply` kind；只看
   `delivered_at IS NULL`，因此终态未 ACK 事件也能被原 consumer 收敛。
3. 结果按 Installation UUID 排序、去重，最多 100；第 101 项 fail closed。
4. 不从 active binding 创建 descriptor。进程重启后没有 live session 的 active binding 不能被冒领。
5. factory 只接受 exact descriptor、`PreparationWorker` 和 `LivePreparedJobDirectory`，并复用同一
   connector/scope；不缓存、不启动 job。
6. 跨租户 descriptor、伪类型、错误 DB role、脏连接和越界结果全部拒绝。

## 修改目录

- `services/aos-api/aos_api/extension_runtime/pending_preparation_directory.py`
- `services/aos-api/tests/extension_runtime/test_pending_preparation_directory.py`
- `services/aos-api/tests/extension_runtime/test_pending_preparation_directory_pg.py`
- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/`
- `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/closure-manifest.md`

## 退出条件与下一波

目录/factory 的纯合同、真实 18432 租户隔离、hash、closure 验证和 m1 提交全部通过。下一波实现保留
live owner 的有界 scheduler：新建只源于 pending apply，apply ACK 后继续保留本进程 owner，assignment
撤销或进程停止时收敛清理。
