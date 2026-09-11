# Live installation scheduler 方案

日期：2026-09-12

## 目标

在一个 TenantScope 内管理本进程创建的 `LiveInstallationLifecycleOwner`。每个 tick 先读取 pending-apply
descriptor，为新 Installation 创建 owner，然后按 UUID 顺序持续 tick 全部已拥有 owner。apply outbox 被
ACK 后 descriptor 会消失，但现存 owner 必须继续保留，以承接后续 verify/enable 和 installed package
调用。

## 军规

1. 只接受 exact `PostgresPendingPreparationDirectory` 与 `LiveInstallationOwnerFactory`，两者 TenantScope
   必须一致。
2. owner cache 最多 100，键为 descriptor Installation UUID；同键只创建一次。
3. descriptor 消失不代表授权撤销，也不停止 live session。
4. tick 固定 UUID 顺序、单任务串行；目录或任一 owner 失败即停止当前 tick，不继续后续 owner。
5. caller cancellation 不能取消 scheduler 持有的 tick。
6. `revoke(installation_id, expected_owner)` 必须 identity 匹配，先等待当前 tick，再从 cache 删除并停止
   原 owner；避免旧调用撤销替代 owner。
7. `stop()` 先等待 tick，再从 cache 隔离全部 owner并逐一 stop；一个 stop 失败仍清理其余 owner，最后
   抛出首个错误。进入 stop 后拒绝 tick/revoke。
8. scheduler 不读取权限、不 ACK、不创建 worker，不处理 disable outbox。production 编排必须在
   disable cleanup 之前明确 revoke live owner。

## 修改目录

- `services/aos-api/aos_api/extension_runtime/live_installation_scheduler.py`
- `services/aos-api/tests/extension_runtime/test_live_installation_scheduler.py`
- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/`
- `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/closure-manifest.md`

## 验证和下一波

验证创建一次、descriptor 消失仍保留、排序、上限、失败短路、并发、取消、identity revoke、全量清理。
通过后提交。下一波扩展 runtime assignment/host：recovery first，lifecycle scheduler second，configure
third，live owner revoke then disable last，并在 assignment revision 替换/删除时停止旧 scheduler。
