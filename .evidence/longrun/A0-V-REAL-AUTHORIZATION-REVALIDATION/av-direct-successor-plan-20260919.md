# AV 直继实例与 1800 秒修复装载方案

## 父权威与目标

AU 因 runtime-apply Health observation 过期被正式 owner 安全冻结，随后通过唯一 disable operation
`51bdbc84-901f-448d-87e8-5a655790e0d3` 正式退休。Binding 终态为 rev9/epoch5 disabled/fenced，三项资源
released，九路回 legacy rev116/group143；exact detach Receipt 为
`7e223943-906f-4efe-8d4b-da7fc2424e48`，content hash 为
`sha256:a3155cdf8c5fe13995faac9de8f6d8eedbf83609239303f09d9fcee8119bdfb1`。

definition 保持 rev73 disabled，AU attempt=0；十二 Run 与十二 Dataset Receipt 保留，Store Receipt、
`ecom_link`、projection pending、in-flight 与 canary 均为零。AV 只能从上述 exact detach Receipt 创建，
不得复用 AU identity，不得启动 snapshot worker 或调用 `run_definition`。

## 文件级清单

1. `scripts/a0v_av_replacement_recovery.py`：锁定 AU 正式退休、exact detach Receipt、legacy rev116/group143，
   完成 AV create/prepare/verify/stage/configure/enable；immutable intent 已存在时只读核账，不重发。
2. `scripts/a0v_av_successor_business.py`：只接受 Owner 实际签发的 AV installation/generation/configuration 与
   AU exact detach Receipt，登记 successor 时 definition 仍 disabled、attempt=0。
3. `scripts/a0v_av_successor_cutover.py`：固定 approval/prepare/pause/commit/validate/resume，目标 extension
   rev117/group144，externalEffectsAllowed=false。
4. `scripts/a0v_av_health_observation.py`：在唯一 Runtime Host 装载 1800 秒 recoverable Store 上限后，只读锁定
   AV、九路、三资源、零 attempt/在途/canary，并要求至少 12 次新增健康续租。
5. 对应专项测试锁定 predecessor、Receipt/hash、版本、路由 revision、definition rev73 disabled、1800 秒上限及
   禁止 `run_definition`；verification 记录所有正式身份、Receipt 与终态。

## 串行执行与停止条件

1. 先读回 AU 唯一 disable operation、两张 lifecycle Receipt、detach hash 及零副作用边界；任一漂移立即停止。
2. 依次执行 AV preflight/create/prepare/verify/stage/configure/enable；创建与 stage 后只采用 Owner 实际签发身份。
3. 登记前必须确认 AV Binding rev4/epoch3 enabled/ready/unfenced、三资源 pending、四项 installation operation
   succeeded、全租户 running/unresolved/runtime pending=0、canary=0，definition rev73 disabled。
4. successor registration 后完成 cutover 六阶段；终态必须为 Binding rev6/epoch3 ready、九路 extension
   rev117/group144、definition rev73 disabled、attempt=0。
5. Runtime Host 必须唯一，读回 `recoverableStoreExecutionLimitSeconds=1800`；连续观察至少 12 次新增续租，
   全程 AV attempt=0、资源 3/3 健康，第二 Runtime Host 数量为 0。
6. 专项/累计测试、Python 编译、差异检查、8434/18181 只读复验、verification 与 commit 完成后，下一波才可
   进入 frozen snapshot transfer/renew 与自然 worker 领取。

任何未知结果、未知 Receipt/hash、非零 attempt/canary、双 Runtime Host、definition 非 disabled 或端口状态漂移，
都立即冻结边界；不得重发、不得延长等待越权、不得修改 AU 或十二 Run 的既有记录。230 L0 继续挂起，不 push。
