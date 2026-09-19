# BF 直系后继与单 Host 激活方案

## 父权威

BE installation `1a0f801f-d8f3-43af-a31e-5c9fc8161d6d` / generation
`93349d9b-ad61-4919-9cbd-e1e9b02545bb` 已由唯一 disable operation
`dbe83c13-de44-4f49-8834-c6ac0a662782` 正式退休：Binding rev8/epoch4 disabled/fenced/unknown，三资源
released，九路 legacy rev143/group170，detach lifecycle 为 exact `fence → detach` 两张 Receipt；detach Receipt
`2b758ca2-8afd-48a4-af23-6367fe505758` / hash
`sha256:db4450919ba39f8443aa20eb0a8b0d9be27eda5a17c40a069b17a0637e91651d`。definition rev97 disabled，
唯一 terminal attempt 已冻结，Store/link/projection/canary 全零。

BF 只能从该 exact BE detach authority 创建，不复用 BE identity、attempt 或 snapshot worker。

## 文件与控制范围

1. `scripts/a0v_bf_replacement_recovery.py`：复用既有 replacement Owner，锁定 BE exact detach、lock、
   rev143/group170、definition rev97，创建全新 BF installation/generation/configuration。
2. 创建完成后，新增 `scripts/a0v_bf_successor_business.py` 与 `scripts/a0v_bf_successor_cutover.py`：只在 BF
   enable 正式 succeeded 后 register/cutover，目标九路 extension rev144/group171。
3. 沿用当前唯一前台 Runtime Host；启动/执行前证明第二 Host=0，不使用 KeepAlive，不启动 Cron 或 snapshot
   worker。
4. 专项测试固定前驱 detach、路由版本、definition 与禁止 `run_definition`。

## 串行步骤与停止条件

1. preflight/create 固定 BE detach、legacy143/group170、definition97 disabled、attempt0 与业务零副作用；创建 BF
   后固定新 identity。
2. 保持唯一 Host，执行 prepare；只读等待 apply 正式 succeeded 后才执行唯一 verify；verify succeeded 后连续
   stage/configure/enable，避免健康观察过期。
3. enable 必须正式 succeeded，Binding 达 rev4/epoch3 ready/enabled/unfenced，三资源 live；任何 stale/unknown
   立即停止，不重发 enable。
4. enable 成功后 register，并串行 approve/prepare/pause/commit/validate/resume；终态九路 extension
   rev144/group171，definition 仍 rev97 disabled。
5. 记录至少 12 次新增健康续租，verification 落盘、测试与精确提交后，才进入 BF saved-snapshot recovery。

全程不读商城源数据、不启动 snapshot worker、不手工 `run_definition`；十二 saved Run/Receipt 保留，230 L0
挂起，`dev-org/dev-project` 仅零 canary，不 push、不动其他分支。
