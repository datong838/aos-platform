# BJ 直系后继与单 Host 激活方案

## 父权威

BI installation `8ca245a1-8420-4590-b9e4-f92256fc22ce` / generation
`6f527122-a4a5-4056-a4e6-ca888f4b64d7` 已由唯一 disable operation
`96f687af-97ea-44cc-97e6-0c1cd292a8cf` 正式退休：Binding rev8/epoch4 disabled/fenced/unknown，三资源
released，九路 legacy rev155/group182，detach Receipt `64375b18-389a-4e5b-bd17-c7e03a63edd6` / hash
`sha256:0962da63b333d3bf94ea9cd9272e2aeba8afad44e3c678c560b4bd4872b56ddd`。definition rev109 disabled，
唯一 abandoned terminal 已冻结，Store/link/projection/canary 全零。

BJ 只能从该 exact BI detach authority 创建，不复用 BI identity、attempt 或 snapshot worker。

## 文件与控制范围

1. `scripts/a0v_bj_replacement_recovery.py`：复用既有 replacement Owner，锁定 BI exact detach、lock、
   rev155/group182、definition rev109，创建全新 BJ installation/generation/configuration。
2. 创建完成后新增 BJ successor business/cutover/health wrapper；只在 enable 正式 succeeded 后 register/cutover，
   目标九路 extension rev156/group183。
3. 沿用当前唯一 Runtime Host PID 10991；启动/执行前证明第二 Host=0，不使用 KeepAlive，不启动 Cron 或
   snapshot worker。
4. 专项测试固定前驱 detach、路由版本、definition 与禁止 `run_definition`。

## 串行步骤与停止条件

1. preflight/create 固定 BI detach、legacy155/group182、definition109 disabled、唯一 terminal attempt 与业务零副作用；
   创建 BJ 后固定新 identity。
2. 保持唯一 Host，执行 prepare；apply 正式 succeeded 后才执行唯一 verify；随后连续 stage/configure/enable。
3. enable 必须正式 succeeded，Binding 达 rev4/epoch3 ready/enabled/unfenced，三资源 live；任何 stale/unknown 停止。
4. register 后串行 approve/prepare/pause/commit/validate/resume；终态九路 extension rev156/group183，definition
   仍 rev109 disabled。
5. 记录至少12次新增健康续租，verification、测试与精确提交后才进入 BJ saved-snapshot recovery。

全程不读商城源数据、不启动 snapshot worker、不手工 `run_definition`；十二 saved Run/Receipt 保留，230 L0
挂起，`dev-org/dev-project` 仅零 canary，不 push、不动其他分支。
