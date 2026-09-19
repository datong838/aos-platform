# AY 直系后继方案

## 父权威与目标

AX disable operation `8589a12c-aec2-4035-8937-f358dd1a8488` 已终结，detach Receipt
`622c8e25-ec0f-40dd-bf1f-ea57d180a800`，content hash
`sha256:583954da94992d30f7c5f9133c235eb3b17e0d8d190c27d61fe47621d41a6870`；九路均为 legacy
rev125/group152。AY 只能从该 Receipt 创建，不复用 AX installation/generation。

策略 authority 保持 current runtimePolicy rev9。AY 必须在全新 installation/configuration/generation 中引用 current
authority。definition rev79 disabled 保持，不启动 qcursor/snapshot worker，不读取商城源数据。

## 文件级清单

1. `scripts/a0v_ay_replacement_recovery.py`：固定 AX detach、安装创建、prepare/verify/stage/configure/enable 与观察。
2. 创建阶段由 Owner 签发 AY installation；stage 阶段由 Owner 签发 generation/configuration，随后将 exact identity
   固定到 `scripts/a0v_ay_successor_business.py`。
3. `scripts/a0v_ay_successor_business.py`：只接受 AX detach Receipt 与 legacy rev125/group152，登记 AY generation。
4. `scripts/a0v_ay_successor_cutover.py`：固定 approval/prepare/pause/commit/validate/resume，目标 extension
   rev126/group153，外部效果关闭；operation ID 仅在方案内生成一次并由专项测试锁定。
5. `scripts/a0v_ay_health_observation.py`：只读记录冻结基线后至少 12 次新增 `runtime_lease_renewed`；全程锁定
   attempt=0、三资源、九路、在途与 canary 为零。
6. 对应专项测试固定 predecessor、Receipt、版本、路由与禁止 `run_definition`。

## 串行步骤与退出条件

依次 preflight/create/prepare/verify/stage/configure/enable；登记前确认 Binding rev4/epoch3 ready、三资源 pending、
全部 installation operation succeeded、全租户无 running/unknown/pending、canary0。随后 register 与 cutover 六阶段，
终态要求 Binding rev6/epoch3 ready、九路 extension rev126/group153、definition 仍 rev79 disabled。

切换后记录续租基线并要求至少新增 12 次健康续租。任何 immutable intent 已存在、Receipt/hash 漂移或未知提交均
只读核账，不换键重发。verification 落盘并精确提交后才进入 AY saved-snapshot recovery；不 push，230 L0 挂起。
