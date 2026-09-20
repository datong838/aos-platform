# CB 正式退休与 CC direct successor verification（2026-09-21）

## 1/6 plan 与基线

`CC_DIRECT_SUCCESSOR_GREEN`。HEAD 基线 `4eb4184b`；CB 唯一 attempt
`727af369-a8ce-4500-86a7-1cf412a42cb3` 为 failed rev4，原因
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；definition rev151 disabled、recovery49。
本波未读取商城源数据，未创建业务 attempt，未写负租户，未启动 18181 API 或 snapshot worker，未调用
`run_definition`。

## 2/6 CB Host 释放与正式退休

- CB installation/generation：`3d6df614-5a05-4c6f-823e-688d81e84096` /
  `0cceac8c-c831-4b3f-92c3-fc35240c5414`；原 Host PID 36215 一次 SIGTERM 后正常退出，读回 binding
  rev7/epoch4 disabled/fenced/desired enabled 与 3/3 resources released。
- disable operation `6695a5a7-e5e6-4662-ad06-9495f9ed3e9a`；fence Receipt
  `a16c19af-048b-4b03-bcc0-b730fea349b7`，content hash
  `sha256:71d98a713c8d0f93f2644eb108187cf3529bb5d5b095ce8adc70cfe9b8cc947a`。
- detach Receipt `087eed56-f46c-4a9b-bc57-ba24e2e78d04`，content hash
  `sha256:ab3661056826d5a9998c8ba55d278317429fcb9286b7efa65fca467c2615be49`。
- 最终 CB binding rev9/epoch5 disabled/fenced/desired disabled；九路 legacy rev209/group236。
  这里的 group236 仅为 cutover group revision，230 L0 仍保持挂起。

## 3/6 CC 创建与 lifecycle

- CC installation/generation：`03942567-0f78-4530-b9dd-634bec59c780` /
  `c1ffee4f-c13b-4d1a-93d2-c3b35bd66ca2`；lock
  `sha256:e90cdcbf95f12f2edcc711c51e55c67ad938364d894c40f0cf33d7f41313010b`。
- prepare/verify/configure/enable operation：`d3bcdc60-c9b8-4afa-84d8-fe9441abafc1`、
  `2451ee2b-060e-4d7d-b26d-3f2de7696688`、`15090f1f-481f-4bca-bf72-23a054d2c73a`、
  `a9c24b41-5781-4cfb-a591-9d4470889498`，均 succeeded。
- configuration `c6ca556d-6fc3-4eb1-9956-b66b4901caf3` /
  `sha256:773b1775a075582b47f464a9367d3c0b17b732e0b28f340e5631cd7d8f522bf5`；最终 lifecycle
  binding rev4/epoch3 enabled/ready，3/3 live resources。

## 4/6 注册与九路 cutover

- registration Receipt `d62c89a6-da4e-429b-b6e2-1458f920fa34`，request hash
  `sha256:546361d54603667a7d270685ec661ea309b09c4f6ad136c3ba96aa848c615006`，content hash
  `sha256:e4d6a15e6ffff54e434870922584813e735a4297a9a19f4290f0596719efc33e`。
- cutover operation `7cd9744d-fdee-46a9-b152-1bfa6129c77d`；prepare/pause/commit/validate/resume
  Receipts 依次为 `e09a081f-c2c1-4c90-bb6c-40f9a2f353f4`、
  `41efd0c3-8a47-40e9-93a0-680e6c434091`、`943c5e46-3559-4f40-9b41-7e7af9efee8d`、
  `f5c9c116-442e-4f68-a454-7d325b28714e`、`ae9bd9ae-9073-4fd5-b779-251a36a6d6fe`。
- 对应 content hash 依次为 `sha256:043aabf36d6e9f3273d8c883d3442e7f120420fb09143029e8ce83502c60180b`、
  `sha256:4d6a38b9430701da7d66572018df243faa4bb88b184bc5a4ed890aedbfdeb444`、
  `sha256:4fd5a69f536abdfb3d7d1c22db60e3f71faac4cdc3db0c8f61a0d345a01a2e0f`、
  `sha256:5fd02c137800ada8c037251e7f2e88da5a376389605c43fb80725394c49d1bc7`、
  `sha256:be32717919380c25a7c6f988fc54a6634cac3d72f77685b26f1b2aa6b086b154`。
- 最终 CC binding rev6/epoch3 enabled/unfenced/ready；九路 extension rev210/group237。

## 5/6 唯一 Host 与健康观察

- 唯一外置 Host PID 38020，状态文件 liveTargets 仅 CC；第二 Runtime Host=0、18181 listener=0、
  snapshot worker=0。
- 只读 repeatable-read 健康观察从 renewals=3 到 15、last sequence=16 到 28，target delta=12，
  36 samples；三资源始终 pending、未释放、未过期，最终 expires_at
  `2026-09-20T19:18:01.255341Z`。
- definition rev151 disabled；CC attempt=0；全局 running attempt=0、unresolved=0、runtime pending=0、
  canary=0。

## 6/6 验证与下一波

- snapshot members=12、running saved Run=12、Dataset Receipt=12；Store Receipt=0、`ecom_link`=0、
  projection pending=0。
- 新增逻辑仅为 CB 正式退休、CC 固定边界包装器与只读健康观察器，生产实现未修改；测试锁定 failed
  boundary、detach、lifecycle、registration、cutover 和 repeatable-read 观察，均禁止 `run_definition`。
- `py_compile`、完整约束测试与 `git diff --check` 作为提交前门禁。下一波自动执行 CC saved-snapshot
  recovery：保持 PID 38020 在线，证明第二 Host=0、18181=0、snapshot worker=0，再按纯 HTTP transfer
  rev152 / recovery50 / definition rev153 enabled、关端口后唯一自然 worker 与 terminal pause rev154 规则串行执行。
