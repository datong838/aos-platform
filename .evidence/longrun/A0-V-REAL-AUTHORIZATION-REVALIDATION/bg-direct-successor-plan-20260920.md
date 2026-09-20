# BG 直系后继与单 Host 激活方案

## 父权威

BF installation `98a16beb-6342-48bd-9e12-989f3612ca00` / generation
`e33e0a9e-7296-4374-9aa9-113f1ed79b5f` 已由唯一 disable operation
`da0a2b14-f0f7-4f21-8513-c56bf4fbeb29` 正式退休：Binding rev8/epoch4 disabled/fenced/unknown，三资源
released，九路 legacy rev146/group173，detach Receipt `03852ebe-20e0-4a41-a5fc-c9eb3aa927dd` / hash
`sha256:ff354c79889453d270baa1b722abdb8785493f7f9432aa42fbe5b6ac7a61c925`。definition rev100 disabled，
双 terminal attempt 已冻结，Store/link/projection/canary 全零。

BG 只能从该 exact BF detach authority 创建，不复用 BF identity、attempt 或 snapshot worker。

## 文件与控制范围

1. `scripts/a0v_bg_replacement_recovery.py`：复用既有 replacement Owner，锁定 BF exact detach、lock、
   rev146/group173、definition rev100，创建全新 BG installation/generation/configuration。
2. 创建完成后新增 BG successor business/cutover/health wrapper；只在 enable 正式 succeeded 后 register/cutover，
   目标九路 extension rev147/group174。
3. 沿用当前唯一前台 Runtime Host；启动/执行前证明第二 Host=0，不使用 KeepAlive，不启动 Cron 或 snapshot worker。
4. 专项测试固定前驱 detach、路由版本、definition 与禁止 `run_definition`。

## 串行步骤与停止条件

1. preflight/create 固定 BF detach、legacy146/group173、definition100 disabled、双 terminal attempt 与业务零副作用；
   创建 BG 后固定新 identity。
2. 保持唯一 Host，执行 prepare；apply 正式 succeeded 后才执行唯一 verify；随后连续 stage/configure/enable。
3. enable 必须正式 succeeded，Binding 达 rev4/epoch3 ready/enabled/unfenced，三资源 live；任何 stale/unknown 停止。
4. register 后串行 approve/prepare/pause/commit/validate/resume；终态九路 extension rev147/group174，definition
   仍 rev100 disabled。
5. 记录至少12次新增健康续租，verification、测试与精确提交后才进入 BG saved-snapshot recovery。

全程不读商城源数据、不启动 snapshot worker、不手工 `run_definition`；十二 saved Run/Receipt 保留，230 L0
挂起，`dev-org/dev-project` 仅零 canary，不 push、不动其他分支。
