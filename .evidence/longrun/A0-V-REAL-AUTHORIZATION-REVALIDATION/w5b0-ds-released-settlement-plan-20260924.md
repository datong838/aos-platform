# W5b0 DS Released Owner 正式 settlement 计划（2026-09-24）

## 现状与方案依据

W5a2 `8af6ecd9` 已将当前 RuntimePolicy 推至 rev13；DS (`c6812824-a0c3-4adc-9ebc-d56178ae135c`) 仍 active/etag5，binding rev7/epoch4、desired enabled/observed unknown、enabled false/fence true，三个资源已 released、四个旧 operation 均 terminal。`require_released_owner_settlement` 只读返回 etag5/rev7；旧定义 rev3 disabled、新定义不存在，12 个 schedule disabled、DS 12 个 selection 的 `expiresAt` 已是 2026-09-23T11:59:16Z，活跃 DS attempt 0。现行 `options()` 阻于配置 policyRef rev12，不得复用旧 W5 controls/options。

复习 `ecommerce-runtime-host-and-growth-1.5-replacement-plan.md`、`w5a2` 验收、正式 `RuntimeDisableService`/`RuntimeDisableConsumer` 与先前 AJ Released Owner 退休实现。本波只用原 Owner disable/consumer 把 DS 从“已释放但 unknown/fenced”确定性落为 disabled，**不退役 Installation、不重配、不启用、不读商城源**。

## 文件与串行步骤

- 新增 `scripts/a0v_w5b_ds_settlement.py` 和 `services/aos-api/tests/extension_runtime/test_a0v_w5b_ds_settlement.py`，私有 state 为 `.../20260924-w5b0-ds-settlement/`；仓内只落计划、去敏 verification。
1. 只读快照：精确 DS ID/generation/lock/etag/binding/operation/resource、attempt=0、12 schedules disabled、旧定义 disabled/new absent、canary=0。核对 8080 和 m1，私有目录此前不存在；只保存运行控制元数据，不保存商城 source payload。
2. 冻结一次性 disable intent（O_EXCL 0600）：固定 `a0v-w5b0-ds-settle-released-20260924-v1`、etag5、generation、binding rev7；用 `require_released_owner_settlement` 再校验。任何未知/既存键先只读对账。
3. 由原 `RuntimeDisableService.request` 一次接受，独立回读同一个 operation_id 和 Owner receipt；如已被独立 Host 处理，按正式状态核对，不重复 request。
4. 仅 claim 精确 DS disable outbox 后用原 `RuntimeDisableConsumer.finish_claimed` 完成；若已处理，则正式回读，不 claim 其他安装。任何未知 lease/delivery 边界不重新 claim，冻结。
5. 独立审计 DS binding desired disabled、enabled false/fence true、disable operation succeeded/outbox acknowledged，资源仍 released、attempt=0、12 schedules disabled、canary=0；主库当前治理 rev13 不变。写 verification，测试，提交 m1，不 push。

## 停止与下一波

任何请求结果未知、非精确 operation/lease、未终结旧操作、资源回收漂移、业务 attempt 新增、canary 非零即停止并只读对账，不重复命令。完成后 W5b1 才可追加 DS 同族 Configuration rev2（当前 Policy rev13），再走正式 configure/enable；W5b2 才处理 12 条已过期 selection 的新 successor 与调度定义。
