# AZ 直系后继与单 Host 快速激活方案

## 父权威与现场修正

AX 仍是最后一个拥有正式 dispatch detach authority 的路由前驱：installation
`be884663-0dba-4d9b-aa56-84caaf01147d`、generation `a14c911b-6796-4d22-a3b0-1817cf502de9`、
disable `8589a12c-aec2-4035-8937-f358dd1a8488`、detach Receipt
`622c8e25-ec0f-40dd-bf1f-ea57d180a800` / hash
`sha256:583954da94992d30f7c5f9133c235eb3b17e0d8d190c27d61fe47621d41a6870`；九路 legacy
rev125/group152。

AY 是 AX 的失败叶子，现已用 configured-unactivated Receipt
`48fc0e55-578d-46ae-b45a-bf8ab8085823` / hash
`sha256:21494a12aed250565b7f65cf4b8da0a36a5d9d9c8c9cbb433bd2346734df4409` 正式退休为
uninstalled@6。AZ 必须同时证明 AX detach 与 AY 退休，才能作为 AX 的新叶子创建；不得把 AY 当成 detach 前驱，也不得
复用 AY identity。

AY enable 日志已定位 `HealthObservationStale`：verify 与 enable 间隔过长，且旧
`com.aos.a0v-runtime-u` KeepAlive Host 会反复拉起。该 launchd 项已经 bootout，当前 Host=0。本波不恢复它。

## 文件与控制范围

1. `scripts/a0v_az_replacement_recovery.py`：复用既有 replacement Owner，但 preflight 额外锁定 AY 退休
   Receipt；创建全新 AZ installation/generation/configuration。
2. `scripts/a0v_az_successor_business.py`、`scripts/a0v_az_successor_cutover.py` 与 health observer：只在 AZ
   enable 已正式 succeeded 后使用，目标 extension rev126/group153，definition rev79 disabled。
3. 单个前台 Runtime Host 使用当前已签名 bundle/trust roots 和 AZ 独立状态文件；启动前必须证明 launchd 项不存在、
   Runtime Host 进程数为 0。不得启动第二 Host，不使用 KeepAlive。
4. 对应专项测试锁定双父权威、零 Host 基线、路由版本和禁止 `run_definition`。

## 串行执行与退出条件

1. preflight/create：核验 AX detach、AY configured-unactivated Receipt、legacy125/group152、definition79 disabled、
   attempt0 与业务零副作用；创建 AZ 后固定 identity。
2. 启动唯一前台 Host；只接受一个精确 PID/状态文件。随后执行 prepare 与 verify，均须正式 succeeded。
3. verify 成功后不插入观察等待，连续执行 stage/configure/enable；enable 必须在 fresh-health 窗口内由同一 Host 推进到
   succeeded，Binding 达 rev4/epoch3 ready/enabled/unfenced，三资源 pending/observed running。
4. 若出现 `HealthObservationStale`、Host 退出、accepted 超时或未知提交，立即停止：只读冻结 AZ，不重发 enable，
   不 register/cutover，走正式退休+后继。
5. enable 成功后才 register，并完成 cutover approval/prepare/pause/commit/validate/resume；终态九路 extension
   rev126/group153，definition 仍 rev79 disabled。
6. 记录至少 12 次新增健康续租；verification 落盘、测试与 `git diff --check` 通过并精确提交后，才进入 AZ
   saved-snapshot recovery。

全程不读商城源数据、不启动 Cron/snapshot worker、不手工 `run_definition`；12 个 saved Run/Receipt 保留，230 L0
挂起，`dev-org/dev-project` 仅零 canary，不 push。
