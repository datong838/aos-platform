# AR direct successor 与 saved snapshot 续接方案

## 上位 authority

AQ 已通过 operation `e45d1c14-ebe0-43e0-bd24-75feb26a9a69` 正式 detached；detach Receipt
`5de8ea90-3a52-4556-af26-8c008044cb77`，hash
`sha256:201556d70b44750c0fed8ad71aa09c718b27faf6aa5aeb5d2f36fe4a4ddb098e`。九路由为 legacy
revision104/group131，三资源 released，definition rev66 disabled，唯一 AQ attempt 已失败且 Store 副作用为零。
Runtime Host PID 93413 已在 strict-link 批量修复 `2ce96305` 后启动并健康，qcursor 保持停止。

## 文件级清单

1. `scripts/a0v_ar_replacement_recovery.py`
   - 从 exact AQ detach Receipt 创建唯一 AR installation；
   - 完成 approved → prepared → verified → staged → configured → enabled → observed；
   - 沿用已签名电商 bundle 与固定版本，不新增外部副作用。
2. `scripts/a0v_ar_successor_business.py`
   - 消费 AR exact identity/config 与 AQ detach Receipt，生成 registration-only 请求。
3. `scripts/a0v_ar_successor_cutover.py`
   - 从 legacy group131 经 approve/prepare/pause/commit/validate/resume 切到 AR；
   - externalEffectsAllowed=false、fallbackAllowed=false。
4. `scripts/a0v_ar_saved_snapshot_recovery.py`
   - 从 rev66 disabled definition 迁移既有 frozen group；
   - transfer rev67、renew recovery rev22 并形成 enabled definition rev68；
   - sourceReads=0，不启动 definition。
5. 对应四个 `services/aos-api/tests/extension_runtime/test_a0v_ar_*.py` 与验证证据。

## 执行顺序与停止规则

严格按 replacement preflight/七阶段、successor preview/register、cutover六阶段、snapshot
prepare/schedule-ingest/controls/transfer/renew/enable 执行。任一 immutable intent 已存在、Receipt/hash、路由 revision、
binding、resource、tenant canary 或 snapshot identity 漂移即停止；不得猜测、重发或手工运行 definition。

本波完成条件是 AR active/ready、九路由指向 AR、definition rev68 enabled/recovery rev22 current、12 个 frozen Run
与 Dataset Receipt 保留、sourceReads=0、qcursor 仍停止。下一波才恢复 qcursor，观察唯一 AR 自然 attempt。
