# Live installation lifecycle owner 方案

日期：2026-09-12

## 目标

把单个 Installation 已有的 `runtime-apply -> runtime-verify -> enable` 三段 delivery 放进同一个
进程内异步 owner。owner 必须保留 `PreparationConsumer` 创建的唯一 `PreparedJob`，并让后两段命令
只通过该 job 的签名 session 执行；进程停止时必须等待在途 delivery 收敛，再停止 job 并从
`LivePreparedJobDirectory` 撤销。

本切片只定义并验证单 Installation owner，不做租户/安装发现，不接 production host，不创建 OCI，
也不改变现有 1.4.0 安装与租户数据。

## 军规与边界

1. 构造只接受 exact `PreparationConsumer`，不接受调用方伪造 worker、job、scope 或 installation。
2. 每次 tick 固定顺序运行 preparation、runtime-verify、enable；没有 live job 时后两段不运行。
3. 后两段使用 preparation consumer 同一 trusted connection、scope 和同一个 job；不重新打开 session。
4. 任一阶段抛错立即停止本 tick，不能继续 enable，也不能 ACK 假成功。
5. 调用方取消只取消等待；owner 持有的 tick 继续收敛。`stop()` 先等待 tick，再调用
   `PreparationConsumer.stop()`，从而复用现有 OCI 清理和目录撤销语义。
6. 同一 owner 禁止并发 tick；进入 stop 后拒绝新 tick。
7. 结果只报告三个已有 consumer 的 delivery 结果，不派生新授权。

## 修改目录

- `services/aos-api/aos_api/extension_runtime/live_installation_owner.py`
- `services/aos-api/tests/extension_runtime/test_live_installation_owner.py`
- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/`
- `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/closure-manifest.md`

## 验证

- 固定三段顺序及相同 job/scope/connect。
- 无 job 时不构造 owned consumer。
- verify 抛错时 enable 不运行。
- 并发、取消、stop 收敛与 stop 后拒绝。
- 既有 preparation/owned consumer/live-directory 回归。

## 退出条件

代码、定向测试、方案一致性检查、文件 hash、验证证据、closure manifest 和一次 m1 提交全部完成。
下一波才处理可信安装目录发现和 production 生命周期装配。
