# AZ 两次 terminal attempt 正式冻结方案

## 当前 authority

AZ definition rev81 enabled，但 snapshot worker 已停止且 18181 无监听。唯一自然 worker 留下两个固定 attempt：

1. `5505b051-79f8-47a7-b2e2-4ddfc0893eb1`：revision 61，
   `failed / RECOVERABLE_INGRESS_DEADLINE_EXCEEDED / IngressJournalConflict`；
2. `af15b2e5-7c72-47f0-9e1d-79855a970fd6`：revision 4，
   `abandoned / ATTEMPT_LEASE_EXPIRED`。

十二 Run 仍 running、十二 Dataset Receipt 保留；Store Receipt、`ecom_link`、outbox、projection pending 均为零。
九路 rev126/group153 与三资源仍在，canary=0。此边界不授权重启 worker、第三 attempt 或手工
`run_definition`。

## 文件级变更

1. 将共享 pause-terminal 的 attempt 数量抽为默认值 1；AZ wrapper 唯一覆盖为 2，并只接受 exact
   `ABANDONED_FREEZE_BOUNDARY`，其余十二 Run/Store/link/projection 边界保持原 fail-closed 校验。
2. 专项测试覆盖 attemptCount=2 与禁止 `run_definition`。
3. 执行一次既有 idempotency key `a0v-az-saved-snapshot-pause-terminal-v1`，将 rev81 enabled 原子推进为
   rev82 disabled；结果必须 `sourceReads=0`。
4. inspect 读回 disabled 后落盘 verification 并精确提交。

## 串行步骤与停止条件

1. 读回 snapshot worker 进程=0、18181 listener=0、外部 Runtime Host=1；任一不符立即停止。
2. exact guard 必须为 1 failed + 1 abandoned、attemptCount=2、十二 Run running、Store/link/projection=0、
   routes=9、resources=3、canary=0；任一漂移停止。
3. 执行 pause-terminal；只接受 definition rev82 disabled，不执行其他控制面写入。
4. inspect、专项测试、verification、commit。下一波才允许 AZ 正式 retirement/detach。

全程不读商城源数据、不 push、不动其他分支；230 L0 继续挂起。
