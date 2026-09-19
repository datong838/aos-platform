# AQ direct successor 与 saved snapshot 续接方案

> 执行状态（2026-09-19 14:31+08）：replacement、successor registration、cutover、冻结输入 transfer/renew/enable 均已完成；终态证据见 `aq-direct-successor-verification-20260919.md`。自然 attempt 尚未启动，留给下一波独立守护。

## 上位 authority

AP 已通过 operation `feefe9f4-0dba-442f-a87a-e6b90509c583` 正式 detached；detach Receipt
`bef5442a-eb6d-43bd-b304-6a11ba8463ae`，hash
`sha256:ff3ee5af04d0470b74891dcc8b664afa005358c8ded067ebfe9e6273e0120902`。九路由为 legacy
revision101/group128，三资源 released，definition rev63 disabled，Store 副作用为零。Runtime Host PID 87894
已在 `b287ccbb` 后启动并健康。

## 文件级清单

1. `scripts/a0v_aq_replacement_recovery.py`
   - 从 exact AP detach Receipt 创建唯一 AQ installation；
   - 完成 approved → prepared → verified → staged → configured → enabled → observed；
   - 沿用已签名电商 bundle 与固定版本，不新增外部副作用。
2. `scripts/a0v_aq_successor_business.py`
   - 消费 AQ exact identity/config 与 AP detach Receipt，生成 registration-only 请求。
3. `scripts/a0v_aq_successor_cutover.py`
   - 从 legacy group128 经 approve/prepare/pause/commit/validate/resume 切到 AQ；
   - externalEffectsAllowed=false、fallbackAllowed=false。
4. `scripts/a0v_aq_saved_snapshot_recovery.py`
   - 从 rev63 disabled definition 迁移既有 frozen group；
   - transfer rev64、renew recovery rev21 并形成 enabled definition rev65；
   - sourceReads=0，不启动 definition。
5. 对应四个 `services/aos-api/tests/extension_runtime/test_a0v_aq_*.py` 与验证证据。

## 执行顺序与停止规则

严格按 replacement preflight/七阶段、successor preview/register、cutover 六阶段、snapshot
prepare/schedule-ingest/controls/transfer/renew/enable 执行。任一 immutable intent 已存在、Receipt/hash、路由 revision、
binding、resource、tenant canary 或 snapshot identity 漂移即停止；不得猜测、重发或手工运行 definition。

本波完成条件是 AQ active/ready、九路由指向 AQ、definition rev65 enabled/recovery rev21 current、12 个 frozen Run
与 Dataset Receipt 保留、sourceReads=0、qcursor 仍停止。下一波才启动 qcursor，观察唯一 AQ 自然 attempt。
