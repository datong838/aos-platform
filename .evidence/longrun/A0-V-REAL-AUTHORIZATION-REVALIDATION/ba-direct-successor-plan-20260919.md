# BA 直系后继与单 Host 激活方案

## 父权威

AZ installation `40eee6d9-fb03-4657-a83e-aeb38ec4aeeb` / generation
`7b6befaa-2f92-4e62-85f9-0ca060ec4b90` 已由唯一 disable operation
`06849afe-ee19-486d-9d56-5247e947d8ab` 正式退休：Binding rev8/epoch4 disabled/fenced/unknown，三资源
released，九路 legacy rev128/group155，detach lifecycle 为 exact `fence → detach` 两张 Receipt。definition rev82
disabled，两次 terminal attempt 均已冻结，Store/link/projection/canary 全零。

BA 只能从该 exact AZ detach authority 创建，不复用 AZ identity、attempt 或 snapshot worker。

## 文件与控制范围

1. `scripts/a0v_ba_replacement_recovery.py`：复用既有 replacement Owner，锁定 AZ exact detach、lock、
   rev128/group155、definition rev82，创建全新 BA installation/generation/configuration。
2. `scripts/a0v_ba_successor_business.py` 与 `scripts/a0v_ba_successor_cutover.py`：只在 BA enable 正式 succeeded
   后 register/cutover，目标九路 extension rev129/group156。
3. 沿用当前唯一前台 Runtime Host PID 29815；启动/执行前证明第二 Host=0，不使用 KeepAlive，不启动 Cron 或
   snapshot worker。
4. 专项测试固定前驱 detach、路由版本、definition 与禁止 `run_definition`。

## 串行步骤与停止条件

1. preflight/create 固定 AZ detach、legacy128/group155、definition82 disabled、attempt0 与业务零副作用；创建 BA
   后固定新 identity。
2. 保持唯一 Host，执行 prepare/verify；verify 成功后不插入等待，连续 stage/configure/enable，避免健康观察过期。
3. enable 必须正式 succeeded，Binding 达 rev4/epoch3 ready/enabled/unfenced，三资源 live；任何 stale/unknown
   立即停止，不重发 enable。
4. enable 成功后 register，并串行 approve/prepare/pause/commit/validate/resume；终态九路 extension
   rev129/group156，definition 仍 rev82 disabled。
5. 记录至少 12 次新增健康续租，verification 落盘、测试与精确提交后，才进入 BA saved-snapshot recovery。

全程不读商城源数据、不启动 snapshot worker、不手工 `run_definition`；十二 saved Run/Receipt 保留，230 L0
挂起，`dev-org/dev-project` 仅零 canary，不 push、不动其他分支。
