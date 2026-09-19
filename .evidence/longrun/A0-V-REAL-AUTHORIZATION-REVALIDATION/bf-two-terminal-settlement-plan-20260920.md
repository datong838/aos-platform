# BF 两次 terminal attempt 正式冻结方案

## 当前 authority

BF definition rev99 enabled，但 snapshot worker 已 STOPPED、taskAlive=false 且 18181 无监听。唯一自然 worker
留下两个固定 attempt：

1. `0a79f73d-7243-4778-90af-2e2109115e73`：revision 61，
   `failed / RECOVERABLE_INGRESS_DEADLINE_EXCEEDED / IngressJournalConflict`；
2. `b61340d4-391f-415d-ac77-65ed8f72321d`：revision 10，
   `failed / RECOVERABLE_INGRESS_CANCELLED / IngressJournalConflict`。

二者 request hash 相同、幂等键分别为 `:1` 与 `:2`。此边界不授权重启 worker、第三 attempt 或手工
`run_definition`。

## 文件级变更

1. 将 BF exact guard 收窄为固定两次 terminal history；首个只接受 deadline-failed，第二个只接受
   cancelled-failed，并继续全验十二 Run/Receipt、Store/link/projection、九路、三资源和 canary 边界。
2. BF saved recovery wrapper 的 pause-terminal attempt 数量从 1 收窄为 exact 2；共享默认值仍为 1，不放宽
   其他历史波次。
3. 专项测试覆盖 attemptCount=2、两次 identity/reason 与禁止 `run_definition`。
4. 执行一次既有 idempotency key `a0v-bf-saved-snapshot-pause-terminal-v1`，将 rev99 enabled 原子推进为
   rev100 disabled；结果必须 `sourceReads=0`。

## 串行步骤与停止条件

1. 读回 snapshot worker 进程=0、18181 listener=0、外部 Runtime Host=1；任一不符立即停止。
2. exact guard 必须为 2 failed、attemptCount=2、十二 Run running、Store/link/projection=0、routes=9、
   resources=3、canary=0；任一漂移停止。
3. 执行 pause-terminal；只接受 definition rev100 disabled，不执行其他控制面写入。
4. inspect、专项测试、verification、commit。下一波才允许 BF 正式 retirement/detach。

全程不读商城源数据、不 push、不动其他分支；230 L0 继续挂起。
