# W5c0 Direct Successor 前置权威只读清点（2026-09-24）

## 目标与边界

承接 W5b1R3 `a0370639`：旧 DS enable 已 cancelled，新 disable succeeded，binding rev13/epoch7 disabled/fenced、资源 released、12 schedules off、attempt/canary 0。本波只读识别正式 successor 的安装/签名包/PreparedJob/Host、九路 dispatch detach、12 条 selection/control/预算与旧定义权威，形成下一波实施方案，不创建安装、不启用调度、不读商城源、不发业务 Run。

## 步骤

1. 核对 m1/head/工作树与 `a0v_092`、W5b1R3 两份正式结果；只读 `a0v_w5b_ds_settlement.snapshot()` 与 DB 当前安装 head、锁、overlay、binding、3 lease、所有 operation 终态、detach Receipt、九路 legacy/fenced/gate、12 schedules/attempt/canary。
2. 只读检查现有签名包根/信任根/当前版本、持久 Host 状态和 PreparedJob 目录可见性；不把磁盘旧产物当活实例。核对 replacement Owner 对 `active/etag5 + disabled/fenced + released + terminal operations` 的要求和当前 DS 的匹配度。
3. 只读核对 12 条 selection/control 当前 head 的有效期与安装代际引用、Budget/RuntimePolicy/Price/Model/Route head 的有效性，以及旧/新 definition 当前状态。任何现行权威已过期则下一波先续期，不借旧 plan/keys。
4. 输出 verification/下一波精确任务，m1 commit，不 push。未知、脏状态或任何业务影响迹象仅报告并停写。

## 退出条件

必须能区分“历史已签名包”与“当前 LivePreparedJob”，列明必须串行的 successor 安装、正式卸载、独立 Host prepare/verify/configure/enable、九路路由和 12 条控制链，并指出最早可安全写入的下一步。不得以只读清点称业务恢复。
