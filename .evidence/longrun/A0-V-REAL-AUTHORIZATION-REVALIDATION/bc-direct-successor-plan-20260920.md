# BC 直系后继与单 Host 激活方案

## 父权威

BB installation `09752ccf-d51a-44b7-a5bf-62b5ab8ec5d6` / generation
`099c4d17-47fb-4c07-9ef1-c627ca7b4239` 已由唯一 disable operation
`5e1e9518-eaf1-4fc0-9d6c-30721e342c6a` 正式退休：Binding rev8/epoch4 disabled/fenced/unknown，三资源
released，九路 legacy rev134/group161，detach lifecycle 为 exact `fence → detach` 两张 Receipt；detach Receipt
`0dd16596-c66b-4390-b9dc-0504c1a822c7` / hash
`sha256:023f817fd9c924b05ec59ce011451cef0364061956e8c156cadbc7dfcde73a6a`。definition rev88 disabled，
唯一 terminal attempt 已冻结，Store/link/projection/canary 全零。

BC 只能从该 exact BB detach authority 创建，不复用 BB identity、attempt 或 snapshot worker。

## 文件与控制范围

1. `scripts/a0v_bc_replacement_recovery.py`：复用既有 replacement Owner，锁定 BB exact detach、lock、
   rev134/group161、definition rev88，创建全新 BC installation/generation/configuration。
2. `scripts/a0v_bc_successor_business.py` 与 `scripts/a0v_bc_successor_cutover.py`：只在 BC enable 正式 succeeded
   后 register/cutover，目标九路 extension rev135/group162。
3. 沿用当前唯一前台 Runtime Host PID 29815；启动/执行前证明第二 Host=0，不使用 KeepAlive，不启动 Cron 或
   snapshot worker。
4. 专项测试固定前驱 detach、路由版本、definition 与禁止 `run_definition`。

## 串行步骤与停止条件

1. preflight/create 固定 BB detach、legacy134/group161、definition88 disabled、attempt0 与业务零副作用；创建 BC
   后固定新 identity。
2. 保持唯一 Host，执行 prepare/verify；verify 成功后不插入等待，连续 stage/configure/enable，避免健康观察过期。
3. enable 必须正式 succeeded，Binding 达 rev4/epoch3 ready/enabled/unfenced，三资源 live；任何 stale/unknown
   立即停止，不重发 enable。
4. enable 成功后 register，并串行 approve/prepare/pause/commit/validate/resume；终态九路 extension
   rev135/group162，definition 仍 rev88 disabled。
5. 记录至少 12 次新增健康续租，verification 落盘、测试与精确提交后，才进入 BC saved-snapshot recovery。

全程不读商城源数据、不启动 snapshot worker、不手工 `run_definition`；十二 saved Run/Receipt 保留，230 L0
挂起，`dev-org/dev-project` 仅零 canary，不 push、不动其他分支。
