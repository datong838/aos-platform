# BH 直系后继与单 Host 激活方案

## 父权威

BG installation `c52ab6db-176e-4378-ac88-2ee1bfc58487` / generation
`477c3f92-06f0-4dae-9445-ce6d09c3f462` 已由唯一 disable operation
`95fbec3c-2248-4d43-928c-17b52d3742da` 正式退休：Binding rev8/epoch4 disabled/fenced/unknown，三资源
released，九路 legacy rev149/group176，detach Receipt `48e4d856-6652-4903-af9f-49bf4774bc0d` / hash
`sha256:6302314b46ee2699d9a05ef8552df2932fccb385f29a3442eba64c26458ad1b2`。definition rev103 disabled，
唯一 terminal attempt 已冻结，Store/link/projection/canary 全零。

BH 只能从该 exact BG detach authority 创建，不复用 BG identity、attempt 或 snapshot worker。

## 文件与控制范围

1. `scripts/a0v_bh_replacement_recovery.py`：复用既有 replacement Owner，锁定 BG exact detach、lock、
   rev149/group176、definition rev103，创建全新 BH installation/generation/configuration。
2. 创建完成后新增 BH successor business/cutover/health wrapper；只在 enable 正式 succeeded 后 register/cutover，
   目标九路 extension rev150/group177。
3. 沿用当前唯一前台 Runtime Host；启动/执行前证明第二 Host=0，不使用 KeepAlive，不启动 Cron 或 snapshot worker。
4. 专项测试固定前驱 detach、路由版本、definition 与禁止 `run_definition`。

## 串行步骤与停止条件

1. preflight/create 固定 BG detach、legacy149/group176、definition103 disabled、唯一 terminal attempt 与业务零副作用；
   创建 BH 后固定新 identity。
2. 保持唯一 Host，执行 prepare；apply 正式 succeeded 后才执行唯一 verify；随后连续 stage/configure/enable。
3. enable 必须正式 succeeded，Binding 达 rev4/epoch3 ready/enabled/unfenced，三资源 live；任何 stale/unknown 停止。
4. register 后串行 approve/prepare/pause/commit/validate/resume；终态九路 extension rev150/group177，definition
   仍 rev103 disabled。
5. 记录至少12次新增健康续租，verification、测试与精确提交后才进入 BH saved-snapshot recovery。

全程不读商城源数据、不启动 snapshot worker、不手工 `run_definition`；十二 saved Run/Receipt 保留，230 L0
挂起，`dev-org/dev-project` 仅零 canary，不 push、不动其他分支。
