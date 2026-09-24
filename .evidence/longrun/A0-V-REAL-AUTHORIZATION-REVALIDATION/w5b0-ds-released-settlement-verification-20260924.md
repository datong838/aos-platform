# W5b0 DS Released Owner settlement 验收（2026-09-24）

## 结论

**W5b0 GREEN，禁用由既有正式消费者完成；本地未重复执行。** 按 `w5b0-ds-released-settlement-plan-20260924.md`，仅对 DS `c6812824-a0c3-4adc-9ebc-d56178ae135c` 创建一次原 Owner disable command。其 operation `a71ece36-0abd-486e-972e-8bf69628d2ca` 已正式 `succeeded`，对应 6 条 outbox 事件全部交付；binding rev9/epoch5、desired disabled、enabled=false、fence=true。旧定义仍 disabled，新定义未创建，12 个 schedule 仍关闭、活跃 attempt 0、canary binding 0，三个资源仍 released。

## 串行证据与异常收敛

1. 写前只读：安装 active/etag5/lock exact，binding rev7/epoch4 desired enabled/observed unknown、3/3 资源释放、4/4 旧 operation terminal、12 个 schedule disabled、active attempt 0，`require_released_owner_settlement` 返回固定 etag5/rev7。私有新目录不存在，固定幂等键在 `bundle_installation_command` 为 0。
2. `scripts/a0v_w5b_ds_settlement.py request_disable` 先以 O_EXCL/0600 写精确 intent，随后仅一次 `RuntimeDisableService.request` 返回 accepted/replayed=false，operation ID 如上；主库无第二 disable 请求。
3. 本地 `process_disable` 未取得 lease 并 fail closed，没有再次 request 或 claim。独立数据库只读回读发现 operation 已 `succeeded`，6/6 outbox delivered，首末交付时间 2026-09-24T03:47:41–03:48:12Z；本地 claim 发生在其后。不能凭现有证据给消费者进程命名，但可确认不是本地 `finish_claimed`。新增显式只读 `reconcile` 分支，在完整 `audit()` GREEN 后写 `process-result.json`，标注 `processedByThisExecutor=false`、`resendDisable=false`；没有重入原 claim 路径。
4. 独立 `audit()` 为 `W5B0_DS_SETTLEMENT_GREEN`：binding rev9/epoch5、operation succeeded、6 条 delivered、12 schedule off、attempt 0、canary 0、资源 released。W5a2 治理修订不因本波降级；未读商城源数据、未运行 definition 或业务任务。
5. 新增拒绝已有私有边界、缺失正式 Receipt、活跃 attempt 漂移与并发已完成 reconciliation 测试，4 passed/7 既有 warnings。私有结果文件 0600；`git diff --check` 通过。

## 下一波 W5b1

只针对已 disabled/fenced 的 DS 同族 Configuration `5423ebf3-4928-4950-b55c-ea2662f84bc8` 追加 rev2，精确引用当前 RuntimePolicy rev13；原 rev1/Policy rev12 永久保留。先当前读回五类引用、安装 etag、binding rev9/epoch5、Owner 回执与作业静默，再由正式 Configuration Owner append→configure→enable 分阶段冻结和独立核验。旧 DS 12 selection 到期，**不能**在 W5b1 结束时启用调度定义；W5b2 必须先建新 selection/control/binding successor。未知提交边界只读对账，不补发。
