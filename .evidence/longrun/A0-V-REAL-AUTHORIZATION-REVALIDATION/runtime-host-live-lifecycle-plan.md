# Runtime host live lifecycle 编排方案

日期：2026-09-12

## 目标

让 typed `RuntimeTenantAssignment` 可选持有同 TenantScope 的 `LiveInstallationScheduler`，并把 host tick
固定为 recovery、expired attempt recovery、live lifecycle、configure、disable。disable 必须先 claim
一条 exact lease，再按同 operation 的 Installation identity 撤销 live owner，之后才执行原 disable
executor 与 ACK/retry。

## 设计

1. `RuntimeDisableConsumer` 增加 immutable `ClaimedDisableDelivery`，包含 exact TenantScope、outbox lease 与
   Installation UUID。`claim_once` 只 claim 并读取同 operation routing；`finish_claimed` 重读当前状态、
   执行原 executor、再 ACK/retry。旧 `run_once` 原样组合二者。
2. `LiveInstallationScheduler.find_owner` 只提供当前进程 identity lookup，不返回权限或 session。
3. host 遇到带 scheduler 的 disable consumer 时，先 `claim_once`；若当前 cache 有 exact owner，await
   identity-bound revoke；然后 `finish_claimed`。撤销失败时不进入 executor、不 ACK。
4. assignment lifecycle 必须是 exact scheduler 且 scope 相同。host 追踪实际运行过的 scheduler；assignment
   identity 被替换/删除时先 stop 旧 scheduler。host stop 即使 tick 失败也逐个 stop 全部 scheduler。
5. 每一阶段后重新读取 assignment identity；被撤销的 assignment 不进入后续阶段。
6. 当前 production selector 仍不构造 scheduler；本波只把正确生命周期插槽接入 host，正式 worker
   composition 下一波完成。

## 修改目录

- `services/aos-api/aos_api/extension_runtime/disable_consumer.py`
- `services/aos-api/aos_api/extension_runtime/live_installation_scheduler.py`
- `services/aos-api/aos_api/extension_runtime/runtime_host.py`
- `services/aos-api/tests/extension_runtime/`
- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/`
- `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/closure-manifest.md`

## 退出条件与下一波

旧 consumer 行为回归、exact claim/revoke/finish 顺序、失败零 execute/ACK、replacement/stop cleanup、取消
收敛、PG 回归、hash、closure 和提交全部通过。下一波装配正式 `PreparationWorker` 的签名 Registry
record/artifact reader、schema/current permissions、OCI driver 和 control-plane 唯一 live directory。
