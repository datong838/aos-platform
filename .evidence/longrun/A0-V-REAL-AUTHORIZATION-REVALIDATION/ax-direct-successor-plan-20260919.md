# AX 直系后继方案

## 父权威与目标

AW disable operation `0b77ae08-9c8c-4453-9f2b-709bddaca312` 已终结，detach Receipt
`0c50775b-62fe-4251-81f4-3c9a8709a90e`，content hash
`sha256:22b3fbf13e9fb92d3f7a4744a5f2787c9b0d3adf216727ed01439f1cb18d9226`；九路均为 legacy
rev122/group149。AX 只能从该 Receipt 创建，不复用 AW installation/generation。

策略 authority 已续期到 current runtimePolicy rev9。AX 必须在全新 installation/configuration/generation 中引用 current
authority，避免 AW 的旧 activation refresh 历史冲突。cutover operation 固定为
`900ed51b-9c97-424b-9a19-5e4dc2868f66`。definition rev76 disabled 保持，不启动 qcursor/snapshot worker，
不读取商城源数据。

## 文件级清单

1. `scripts/a0v_ax_replacement_recovery.py`：固定 AW detach、安装创建、prepare/verify/stage/configure/enable 与观察。
2. 创建阶段由 Owner 签发 AX installation；stage 阶段由 Owner 签发 generation/configuration，随后将 exact identity
   固定到 `scripts/a0v_ax_successor_business.py`。
3. `scripts/a0v_ax_successor_business.py`：只接受 AW detach Receipt 与 legacy rev122/group149，登记 AX generation。
4. `scripts/a0v_ax_successor_cutover.py`：固定 approval/prepare/pause/commit/validate/resume，目标 extension
   rev123/group150，外部效果关闭。
5. `scripts/a0v_ax_health_observation.py`：只读记录冻结基线后至少 12 次新增 `runtime_lease_renewed`；全程锁定
   attempt=0、三资源、九路、在途与 canary 为零。
6. 对应专项测试固定 predecessor、Receipt、版本、路由、operation ID，并禁止 `run_definition`。

## 串行步骤与退出条件

依次 preflight/create/prepare/verify/stage/configure/enable；登记前确认 Binding rev4/epoch3 ready、三资源 pending、
全部 installation operation succeeded、全租户无 running/unknown/pending、canary0。随后 register 与 cutover 六阶段，
终态要求 Binding rev6/epoch3 ready、九路 extension rev123/group150、definition 仍 rev76 disabled。

切换后记录续租基线并要求至少新增 12 次健康续租。任何 immutable intent 已存在、Receipt/hash 漂移或未知提交均
只读核账，不换键重发。verification 落盘并精确提交后才进入 AX saved-snapshot recovery；不 push，230 L0 挂起。
