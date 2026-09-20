# BZ 正式退休与 CA direct successor verification（2026-09-21）

## 1/6 plan 与基线

`CA_DIRECT_SUCCESSOR_GREEN`。HEAD 基线 `336b26f3`；BZ 唯一 attempt
`b7044a35-43f8-4089-ba79-4da3d92cbf64` 为 failed rev4，原因
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；definition rev145 disabled、recovery47。
本波未读取商城源数据，未创建业务 attempt，未写负租户，未启动 18181 API 或 snapshot worker，未调用
`run_definition`。

## 2/6 BZ Host 释放与正式退休

- BZ installation/generation：`9b30837c-da4d-4cfd-b438-de40aa5e3d7a` /
  `6f1e6e77-24aa-4052-9102-88e4a432fe55`；原 Host PID 31607 一次 SIGTERM 后正常退出，读回 binding
  rev7/epoch4 disabled/fenced/desired enabled 与 3/3 resources released。
- disable operation `447af99f-fbb2-4142-971d-e5458a90b468`；fence Receipt
  `03ec3eb5-6347-43a5-a348-45a4c6d78f2d`，content hash
  `sha256:0c8639b22525497b193a7b461a4fc45b09fcf4c7affe0bd18ac025136418f4e1`。
- detach Receipt `a5ab50b1-aa8a-4418-9ed9-59a454d9055d`，content hash
  `sha256:3f234f4c5d965b0b824383ff20f980c2f4ed2555c0aab59aac037289b4bfd9eb`。
- 最终 BZ binding rev9/epoch5 disabled/fenced/desired disabled；九路 legacy rev203/group230。
  这里的 group230 仅为 cutover group revision，230 L0 仍保持挂起。

## 3/6 CA 创建与 lifecycle

- CA installation/generation：`0d834ab1-fd2b-4dbc-b9a5-0f0dee712647` /
  `1f18a077-12c6-4242-982a-0c3fa1159540`；lock
  `sha256:00c2ccaa82e00eb0e23f4e7dcd2491b674cb37caaf5d0e1a027709f6c8f47d7a`。
- prepare/verify/configure/enable operation：`69cda7b1-dd65-4fee-b3c1-30225a7a8f3f`、
  `c8128bb5-29b4-44e4-b37f-a2a3455a111a`、`213d2179-6ef7-4707-ab92-c552a37d2946`、
  `a812425b-d128-473f-8230-3853a51dfb72`，均 succeeded。
- configuration `1ce3f7b8-8d08-4e4d-8324-631e259d944b` /
  `sha256:f124e09f3b77296e6fe8873df6880722629b496d40d585bd425dd42bb2f03e15`；最终 lifecycle
  binding rev4/epoch3 enabled/ready，3/3 live resources。

## 4/6 注册与九路 cutover

- registration Receipt `3b163e13-db3d-4928-aa9c-9d20fdda53be`，request hash
  `sha256:de57a9f8c495bbe24c786f7cd964d7bfcae8a6417225386fd52e9b6248ae16a8`，content hash
  `sha256:5fe5a3114ce8c606d15d52cad101bb8da89be8be12876af28d2353b95586c455`。
- cutover operation `551a9424-2d4c-4d0e-88e1-151bb85effd0`；prepare/pause/commit/validate/resume
  Receipts 依次为 `03c288e4-41c9-4679-9672-47bface455a7`、
  `3d96ef66-d930-48ab-8306-82c30d980b28`、`c0af3181-cc6f-41c4-85b4-ed4a854db72b`、
  `b25c0bbe-b1f6-40a4-af28-9621e8fbdecf`、`59394c04-214b-4904-a7ff-3c53030254e2`。
- 对应 content hash 依次为 `sha256:bc12e11608857e5b22c03cbb02a4da4d63289d84b0ed42df358941fd8cb39d4d`、
  `sha256:38d06f3a2ed85f2f0ce2e6897e3b136eb640463ad90c17ccedb02ff9f83f8cad`、
  `sha256:5f757794fb32e84b9fd09d5f395874f96f2e6e0b5ea63900515a4c994701d3cf`、
  `sha256:a62d39fe3706b02d47c68d8a419b4276fbcb47dc318d746f726bd52989de19c8`、
  `sha256:ca77c8e98da9c9633efa66107cfd802736a038cc76fc077a66e4271818a3daba`。
- 最终 CA binding rev6/epoch3 enabled/unfenced/ready；九路 extension rev204/group231。

## 5/6 唯一 Host 与健康观察

- 唯一外置 Host PID 34620，状态文件 liveTargets 仅 CA；第二 Runtime Host=0、18181 listener=0、
  snapshot worker=0。
- 只读 repeatable-read 健康观察从 renewals=3 到 15、last sequence=16 到 28，target delta=12，
  30 samples；三资源始终 pending、未释放、未过期，最终 expires_at
  `2026-09-20T18:22:34.925349Z`。
- definition rev145 disabled；CA attempt=0；全局 running attempt=0、unresolved=0、runtime pending=0、
  canary=0。

## 6/6 验证与下一波

- snapshot members=12、running saved Run=12、Dataset Receipt=12；Store Receipt=0、`ecom_link`=0、
  projection pending=0。
- 新增逻辑仅为 BZ 正式退休、CA 固定边界包装器与只读健康观察器，生产实现未修改；测试锁定 failed
  boundary、detach、lifecycle、registration、cutover 和 repeatable-read 观察，均禁止 `run_definition`。
- `py_compile`、完整约束测试与 `git diff --check` 作为提交前门禁。下一波自动执行 CA saved-snapshot
  recovery：保持 PID 34620 在线，证明第二 Host=0、18181=0、snapshot worker=0，再按纯 HTTP transfer
  rev146 / recovery48 / definition rev147 enabled、关端口后唯一自然 worker 与 terminal pause rev148 规则串行执行。
