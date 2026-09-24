# W5b1R 未消费 enable 的正式取消与回到 disabled（2026-09-24）

## 根因与授权

W5b1 `da5b377d` 已冻结：唯一 enable operation `1d5b0071-3067-456f-8ab5-ee1f666abd83` 超过 deadline 仍 accepted/phase accepted，outbox 1 条未交付、attempt0；binding rev11/epoch6、Config rev2、desired disabled/observed unknown、enabled false/fence true，旧定义和 12 schedules 仍关、活跃 attempt0。进程列表仅 8080 API，未见独立 Runtime Host；正式 `LiveInstallationLifecycleOwner` 的 enable 消费依赖 retained PreparedJob，released DS 不具备。此解释是从代码与运行状态推断，不把它当作已证明的宿主日志事实。

复习 `RuntimeDisableService.request`：对同一 target 的 effect-free accepted/validating enable，可在同事务取消旧 operation、创建 disable Receipt 和 fence；不允许直接改状态或删除 outbox。本波仅按此 Owner 路径关闭悬挂 enable，不创建业务任务、不读商城源、不复用 W5b1 enable 键。

## 目录、文件与步骤

- 新增 `scripts/a0v_w5b1r_enable_retirement.py` 与 `services/aos-api/tests/extension_runtime/test_a0v_w5b1r_enable_retirement.py`；私有状态 `.../20260924-w5b1r-enable-retirement/`，固定新 disable 幂等键 `a0v-w5b1r-retire-unconsumed-enable-20260924-v1`。
1. 只读确认 m1、8080、当前治理 rev13/Config rev2、精确 enable operation/accepted target rev11、outbox attempt0/无 claim/无 delivery、deadline 已过；DS resources 仍 released、active attempt0、12 schedules off、旧定义 disabled、canary0。固定新键在 Command Receipt 为 0，state 目录不存在。
2. O_EXCL/0600 冻结命令 intent（DS etag5/generation/绑定 rev11/旧 enable ID）；用原 `RuntimeDisableService.request` 一次。要求同事务结果：旧 enable `cancelled`、新 disable accepted/Receipt 唯一、binding fenced。未知提交边界只读对账，不重发。
3. 对新 disable 精确 operation：若已有正式消费者完成，走只读 `audit`/reconcile；否则只 claim 该 DS 的这条 disable lease，用原 `RuntimeDisableConsumer.finish_claimed` 一次，未知 lease 不重 claim。不得认领任何 enable outbox。
4. 独立核验旧 enable cancelled（而非 succeeded）、新 disable succeeded、其 outbox delivered、binding disabled/fenced、Config rev2 保留、12 schedules off/attempt0/canary0，旧 enable outbox 不会产生业务 effect；测试、verification、提交 m1。

## 下一波与停止

关闭后不在 DS 内重发 enable。下一波按“正式退休 + direct successor”设计新 active 安装与 live PreparedJob/Host 接续，先解决独立 Host 与资源/控制归属，再复用 W5a2 治理、Config ref 和 12 个新选择的受控新版本。任何状态未知、旧 enable 有 claim/资源效应、或新 disable 不终态，冻结并只读对账。
