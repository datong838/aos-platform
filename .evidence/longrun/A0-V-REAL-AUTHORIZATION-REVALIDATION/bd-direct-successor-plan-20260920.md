# BD 直系后继与单 Host 激活方案

## 父权威

BC installation `3b895c30-34ca-4710-b978-02645d49c83a` / generation
`31776dcd-e28f-4b6d-ae45-75fb0ab5a505` 已由唯一 disable operation
`b713c722-902f-4486-b3bb-4eca02a621b7` 正式退休：Binding rev8/epoch4 disabled/fenced/unknown，三资源
released，九路 legacy rev137/group164，detach lifecycle 为 exact `fence → detach` 两张 Receipt；detach Receipt
`39bb3f98-78b6-444b-9d5c-a51991b03f42` / hash
`sha256:7351a8aca2751c721b96ef1c72352318a507a18598930e13fbc79667f3bc169c`。definition rev91 disabled，
唯一 terminal attempt 已冻结，Store/link/projection/canary 全零。

BD 只能从该 exact BC detach authority 创建，不复用 BC identity、attempt 或 snapshot worker。

## 文件与控制范围

1. `scripts/a0v_bd_replacement_recovery.py`：复用既有 replacement Owner，锁定 BC exact detach、lock、
   rev137/group164、definition rev91，创建全新 BD installation/generation/configuration。
2. 创建完成后，新增 `scripts/a0v_bd_successor_business.py` 与 `scripts/a0v_bd_successor_cutover.py`：只在 BD
   enable 正式 succeeded 后 register/cutover，目标九路 extension rev138/group165。
3. 沿用当前唯一前台 Runtime Host；启动/执行前证明第二 Host=0，不使用 KeepAlive，不启动 Cron 或 snapshot
   worker。
4. 专项测试固定前驱 detach、路由版本、definition 与禁止 `run_definition`。

## 串行步骤与停止条件

1. preflight/create 固定 BC detach、legacy137/group164、definition91 disabled、attempt0 与业务零副作用；创建 BD
   后固定新 identity。
2. 保持唯一 Host，执行 prepare/verify；verify 成功后不插入等待，连续 stage/configure/enable，避免健康观察过期。
3. enable 必须正式 succeeded，Binding 达 rev4/epoch3 ready/enabled/unfenced，三资源 live；任何 stale/unknown
   立即停止，不重发 enable。
4. enable 成功后 register，并串行 approve/prepare/pause/commit/validate/resume；终态九路 extension
   rev138/group165，definition 仍 rev91 disabled。
5. 记录至少 12 次新增健康续租，verification 落盘、测试与精确提交后，才进入 BD saved-snapshot recovery。

全程不读商城源数据、不启动 snapshot worker、不手工 `run_definition`；十二 saved Run/Receipt 保留，230 L0
挂起，`dev-org/dev-project` 仅零 canary，不 push、不动其他分支。
