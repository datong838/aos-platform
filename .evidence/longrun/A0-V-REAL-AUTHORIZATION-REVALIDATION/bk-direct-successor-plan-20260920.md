# BK 直系后继与单 Host 激活方案

## 父权威

BJ installation `2c3972b1-67c1-400d-aa63-b90de369f5de` / generation
`8dafd4ae-d42b-4f2f-accb-b5a49e7c9a3b` 已由唯一 disable operation
`2300de61-0b54-413a-97e7-4e37e3b20768` 正式退休：Binding rev8/epoch4 disabled/fenced/unknown，三资源
released，九路 legacy rev158/group185，detach Receipt `2c5d28d5-cfcc-474d-827d-d0031d0de4d8` / hash
`sha256:9fff94f0bc18f763292002f838bb0f197e9548e59eefe92d2722cd71d307281d`。definition rev112 disabled，
唯一 abandoned terminal 已冻结，Store/link/projection/canary 全零。

BK 只能从该 exact BJ detach authority 创建，不复用 BJ identity、attempt 或 snapshot worker。

## 文件与控制范围

1. `scripts/a0v_bk_replacement_recovery.py`：复用既有 replacement Owner，锁定 BJ exact detach、lock、
   rev158/group185、definition rev112，创建全新 BK installation/generation/configuration。
2. 创建完成后新增 BK successor business/cutover/health wrapper；只在 enable 正式 succeeded 后 register/cutover，
   目标九路 extension rev159/group186。
3. 沿用当前唯一 Runtime Host PID 10991；启动/执行前证明第二 Host=0，不使用 KeepAlive，不启动 Cron 或
   snapshot worker。
4. 专项测试固定前驱 detach、路由版本、definition 与禁止 `run_definition`。

## 串行步骤与停止条件

1. preflight/create 固定 BJ detach、legacy158/group185、definition112 disabled、唯一 terminal attempt 与业务零副作用；
   创建 BK 后固定新 identity。
2. 保持唯一 Host，执行 prepare；apply 正式 succeeded 后才执行唯一 verify；随后连续 stage/configure/enable。
3. enable 必须正式 succeeded，Binding 达 rev4/epoch3 ready/enabled/unfenced，三资源 live；任何 stale/unknown 停止。
4. register 后串行 approve/prepare/pause/commit/validate/resume；终态九路 extension rev159/group186，definition
   仍 rev112 disabled。
5. 记录至少12次新增健康续租，verification、测试与精确提交后才进入 BK saved-snapshot recovery。

全程不读商城源数据、不启动 snapshot worker、不手工 `run_definition`；十二 saved Run/Receipt 保留，230 L0
挂起，`dev-org/dev-project` 仅零 canary，不 push、不动其他分支。
