# AT 直继实例方案

## 父权威与目标

AS disable operation `410d2bcd-3c56-4ea5-af0f-e599a08bc1ba` 已终结，detach Receipt
`ae435475-8932-444b-ab41-9660fb966eaf`，content hash
`sha256:e8d53430e6a52ea3d287d373dc48cd47b7052cffca6c89c531cb8990434d666b`；当前九路均为
legacy rev110/group137。AT 只能从该 Receipt 创建，不复用 AS installation/generation。

AT 创建阶段由 Owner 实际签发 installation `631e6d01-a5bb-4865-95eb-07d5665ed957`；stage 阶段实际签发的
generation `63ea2c87-f185-4b02-b792-1e3073db4a1b` 为后续唯一合法身份，取代施工前预生成的候选 UUID。
cutover operation 固定为
`4062239f-18d4-40a2-990f-64ddbea8e9a6`。definition rev70 disabled 保持，不启动 qcursor/snapshot worker，
不读取商城源数据。

## 文件级清单

1. `scripts/a0v_at_replacement_recovery.py`：exact AS detach、安装创建、prepare/verify/stage/configure/enable 与观察。
2. `scripts/a0v_at_successor_business.py`：只接受 AS detach Receipt 与 legacy rev110/group137，登记 AT generation。
3. `scripts/a0v_at_successor_cutover.py`：固定 approval/prepare/pause/commit/validate/resume，目标 extension
   rev111/group138，外部效果关闭。
4. `scripts/a0v_at_saved_snapshot_recovery.py`：预置冻结输入迁移定义，只有 AT 长续租门槛通过后才允许执行；
   后续恢复 revision23、definition rev72 的 exact 门禁。
5. 对应四个专项测试，锁定 predecessor、Receipt、版本、路由 revision 和禁止 `run_definition`。
6. `scripts/a0v_at_health_observation.py`：只读锁定 AT、九路、三资源、零 attempt/在途/canary，
   从冻结基线连续观察至少 12 次新 `runtime_lease_renewed`；只写私有本地观察证据。

## 执行顺序与退出条件

依次 preflight/create/prepare/verify/stage/configure/enable；登记前确认 Binding rev4/epoch3 ready、三资源 pending、
全部 installation operation succeeded、全租户无 running/unknown/pending、canary0。随后 register 与 cutover 六阶段，
终态应为 Binding rev6/epoch3 ready、九路 extension rev111/group138、definition 仍 rev70 disabled。

切换后记录续租基线并要求至少新增 12 次健康续租，且全过程 attempt=0、资源3/3健康。任何 immutable intent 已存在、
Receipt/hash 漂移或未知结果均只读核账，不重发。专项与累计回归、浏览器只读验收、证据和提交完成后进入保存快照恢复波。
