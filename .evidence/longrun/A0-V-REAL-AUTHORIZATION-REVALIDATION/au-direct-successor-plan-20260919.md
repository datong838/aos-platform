# AU 直继实例与 1800 秒修复装载方案

## 父权威与目标

AT definition 已在 revision73 disabled；四个自然 attempt 均已正式 failed，其中前三个为
`RECOVERABLE_INGRESS_DEADLINE_EXCEEDED`，第四个为停止旧 worker 后的
`RECOVERABLE_INGRESS_CANCELLED`。十二 Run 仍 running，十二 Dataset Receipt 保留，Store Receipt、
`ecom_link`、projection pending 与 canary 均为 0。

AT disable operation `5d69615c-2e9f-4ad5-8725-14a9e1fefd76` 已 succeeded；Binding rev8/epoch4
disabled/fenced，三项资源 released，九路回 legacy rev113/group140。AU 只能从该 operation 的 exact detach
Receipt 创建，不复用 AT installation/generation，也不重发 AT 的任何 Store 幂等键。

本波只完成 AU installation、配置、successor registration、九路 cutover 和新 Runtime Host 对 1800 秒修复的
装载/健康观察。definition rev73 全程保持 disabled，禁止 qcursor/snapshot worker 领取，禁止读取商城源数据。

## 文件级清单

1. `scripts/a0v_au_replacement_recovery.py`：锁定 AT 正式退休、exact detach Receipt、legacy rev113/group140，
   完成 AU create/prepare/verify/stage/configure/enable；所有 immutable intent 已存在时只读核账，不重发。
2. `scripts/a0v_au_successor_business.py`：只接受 AU 的 Owner 实际签发 installation/generation/configuration 与
   AT exact detach Receipt，登记 successor，登记时仍不可执行。
3. `scripts/a0v_au_successor_cutover.py`：固定 approval/prepare/pause/commit/validate/resume，目标 extension
   rev114/group141，externalEffectsAllowed=false。
4. `scripts/a0v_au_health_observation.py`：只读锁定 AU、九路、三资源、零 attempt/在途/canary，并要求至少
   12 次新增 `runtime_lease_renewed`；不得对 definition 执行任何 transition。
5. `services/aos-api/tests/extension_runtime/test_a0v_au_*.py`：锁定 predecessor、Receipt、版本、路由 revision、
   definition rev73 disabled、1800 秒执行上限以及禁止 `run_definition`。

## 串行执行与停止条件

1. 先从数据库读回 AT 唯一 disable operation、两张 lifecycle Receipt 与 detach content hash；任一漂移即停止。
2. 依次执行 AU preflight/create/prepare/verify/stage/configure/enable；创建和 stage 后采用 Owner 实际签发身份，
   不预造 canonical identity。
3. 登记前必须确认 Binding rev4/epoch3 enabled/ready/unfenced、三资源 pending、四项 installation operation
   succeeded、全租户 running/unresolved/runtime pending=0、canary=0，definition rev73 disabled。
4. successor registration 后完成 cutover 六阶段；终态必须为 Binding rev6/epoch3 ready、九路 extension
   rev114/group141、definition 仍 rev73 disabled。
5. 启动唯一新版 Runtime Host，读回其进程装载的 recoverable Store 上限为 1800 秒；连续观察至少 12 次健康续租，
   全程 AU attempt=0、资源 3/3 健康。旧 Runtime Host 必须先退出，第二 Runtime Host 数量必须为 0。
6. 专项/累计测试、Python 编译、差异检查、浏览器只读复验和 verification 落盘后提交。下一波才允许纯 HTTP
   配置与 frozen snapshot transfer/renew，自然 worker 领取前仍禁止手工 `run_definition`。

任何未知结果、未知 Receipt/hash、非零 attempt、非零 canary、双 Runtime Host、definition 非 disabled 或端口状态
不符合预期，都立即停止并冻结边界；不得通过重发、延长等待或修改既有 AT 记录越过。
