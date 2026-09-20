# BL 直系后继与单 Host 激活方案

## 父权威

BK installation `8c78f903-ebd8-4589-97a0-afad76e209e0` / generation
`9ea4ba9d-1ef8-45a6-9060-1e4f37c87038` 已由唯一 disable operation
`6db4b69b-0dbf-4a77-ac71-23cef91c6f50` 正式退休：Binding rev8/epoch4 disabled/fenced/unknown，三资源
released，九路 legacy rev161/group188，detach Receipt `dfce56ec-4bff-4793-a5d5-dab4ad45aa1c` / hash
`sha256:3fc2b8a9c3614912b1ac7a9c0d127677f3cc0187ed5c24209da10a963c71dca4`。definition rev115 disabled，
唯一 cancelled terminal 已冻结，Store/link/projection/canary全零。

BL 只能从该 exact BK detach authority创建，不复用 BK identity、attempt或snapshot worker。

## 文件与控制范围

1. `scripts/a0v_bl_replacement_recovery.py`：复用既有 replacement Owner，锁定 BK exact detach、lock、
   rev161/group188、definition rev115，创建全新 BL installation/generation/configuration。
2. 创建完成后新增 BL successor business/cutover/health wrapper；只在 enable正式 succeeded后 register/cutover，
   目标九路 extension rev162/group189。
3. 当前 Runtime Host=0；create后只启动一个正式 Host，读回第二 Host=0，不使用 KeepAlive，不启动 Cron或
   snapshot worker。完成本波后保持该唯一 Host供下一保存快照波使用。
4. 专项测试固定前驱 detach、路由版本、definition与禁止 `run_definition`。

## 串行步骤与停止条件

1. preflight/create固定 BK detach、legacy161/group188、definition115 disabled、唯一 terminal attempt与业务零副作用；
   创建 BL 后固定新 identity。
2. 启动唯一 Host并执行 prepare；apply正式 succeeded后才执行唯一 verify；随后连续 stage/configure/enable。
3. enable必须正式 succeeded，Binding达 rev4/epoch3 ready/enabled/unfenced，三资源 live；任何 stale/unknown停止。
4. register后串行 approve/prepare/pause/commit/validate/resume；终态九路 extension rev162/group189，definition
   仍 rev115 disabled。
5. 记录至少12次新增健康续租，verification、测试与精确提交后才进入 BL saved-snapshot recovery。

全程不读商城源数据、不启动 snapshot worker、不手工 `run_definition`；十二 saved Run/Receipt保留，230 L0
挂起，`dev-org/dev-project`仅零 canary，不 push、不动其他分支。
