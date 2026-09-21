# CZ 保存快照恢复正式终态验证（2026-09-21）

## 结论

`CZ_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。唯一自然 attempt
`d5ca4825-decb-4263-ac0f-f87d2fe8a7b0` 正式 failed **rev4**，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；worker stop-only 退出，definition
已推进到 rev220 disabled。全过程未读取商城源数据、未调用 `run_definition`、未重发。本波从
CY installation `917cd341-96a5-4428-9508-03c716c587ad` rev217/recovery71 转入 CZ。
本波无页面改动，未开浏览器。

## 1/6 plan 与基线

HEAD `4ccc8179`；CZ `162e4c29-a24e-4c6b-8da7-9582d090d708` / generation
`d1b0f7eb-9677-4d52-a656-a4ae28942976`，binding rev6/epoch3 ready、九路 rev279/group306、
唯一 Host PID 43186；definition 为 CY `917cd341-96a5-4428-9508-03c716c587ad` rev217
disabled、recovery71、attempt=0，12/12 与零副作用。configuration rev1 已引用
RuntimePolicy rev11。

## 2/6 纯 HTTP 18181

`check`/`serve` 读回 Cron=false、snapshot worker=false、进程内 Host=false、sourceCalls=0；
`/v1/health`=200，prepare/schedule-ingest/controls 各确认 12 项，随后 18181 python PID 44621
SIGTERM 释放，第二 Host=0，PID 43186 保持在线。prepare 在 binding rev6/epoch3 上一次通过，
previewHash `sha256:322f6c68e843aa9bd83b9248924e105c206864d187f422f74c261bd3612f7556`。

## 3/6 冻结输入转移

transfer 生成 rev218 disabled/hash
`sha256:7f76086c945295932bf25c0c92785f44f4235a59b1b8472d19e5f7d731bbea5b`；
renew 生成 recovery72/hash
`sha256:acdd751b8801f066feb452481c31e6ab629719a7b6df431c82600204450027ce`；
enable 生成 rev219 enabled/hash
`sha256:19d9f06d324d565ef9a679b52703d97556fdf54dd7e27547b41137a3394f1472`。
manifest 仍为 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，
各阶段 sourceReads=0。

## 4/6 唯一自然 worker

Lease `A0V-CZ-SNAPSHOT-WORKER-20260921` 已在 worker 启动前登记；唯一 worker PID 45019
自然创建上述 attempt，幂等键
`snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
`sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。

## 5/6 连续观察

50 秒只读采样见 running rev2，随后见到 failed rev4；accepted_at
`2026-09-21T16:39:31.770147Z`，completed_at `2026-09-21T16:40:51.467625Z`。
不是 deadline 情形；worker SIGTERM returnCode=-15，未升级 kill。

## 6/6 终态、零副作用与下一波

exact guard 冻结 rev219/recovery72/failed rev4；pause-terminal 生成 rev220 disabled/hash
`sha256:c75ad75d134328a64a34c2f14817d547ccba50154a98156770e7bbfcc6d5730a`。
最终 12 members、12 running Run、12 Dataset Receipt、Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0、worker=0、18181=0，Host PID 43186 仍在。
注意终态为 **rev4**，guard overlay 仍需 predecessor_view revision=4。本提交完成后自动进入
CZ 正式退休与 DA direct successor。不使用定时 wake。本波无页面改动。退休 preflight 前不得
创建 `replacement-da`。
