# BX 正式退休与 BY direct successor verification（2026-09-21）

## 1/6 plan 与基线

`BY_DIRECT_SUCCESSOR_GREEN`。HEAD 基线 `64060ead`；BX 唯一 attempt
`dedb3bf6-46ef-4b25-9733-1197ea043d26` 为 failed rev4，原因
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；definition rev139 disabled、recovery45。
本波未读取商城源数据，未创建业务 attempt，未写负租户，未启动 18181 API 或 snapshot worker，未调用
`run_definition`。

## 2/6 BX Host 释放与正式退休

- BX installation/generation：`45db7b1e-6463-40f2-bf3c-c4e64ce3fd78` /
  `9beb5c99-aba7-4bec-9a10-4f98415aed2f`；原 Host PID 26649 一次 SIGTERM 后正常退出，读回 binding
  rev7/epoch4 disabled/fenced/desired enabled 与 3/3 resources released。
- disable operation `05d32449-7543-4136-afec-9ce7c78c7365`；fence Receipt
  `f41830ec-335f-457d-9674-4aa825e669dd`，content hash
  `sha256:d9ef01a399f42280a055cd1c174d098fa03796b8e639138eb60d4212859af029`。
- detach Receipt `608d36a3-198b-46e2-bc5b-d653e44d44c8`，content hash
  `sha256:1862820a36540eb75b301673e8c5e4553cd1c2f05facf602a35dda4c20754e9c`。
- 最终 BX binding rev9/epoch5 disabled/fenced/desired disabled；九路 legacy rev197/group224。

## 3/6 BY 创建与 lifecycle

- BY installation/generation：`ed64db1a-45eb-442e-8f1b-49ed899731dc` /
  `01f99334-0515-4c73-b442-a293709b3cc2`；lock
  `sha256:77165c48df63d332cebf02dfa35f59711d7d1af5dc5f396db86c23400f3653cc`。
- prepare/verify/configure/enable operation：`5e67db87-80a8-40cc-8a55-38e292f4f7a4`、
  `5e5b243f-4e1b-4f92-8c21-cfe9c3ec499d`、`bb139683-ba82-4fd1-b4d0-c7999a5aa2bb`、
  `a8d7c571-4631-4a3a-a7c7-d7c82628ec8d`，均 succeeded。
- configuration `deb4dc29-2564-4ad8-b1bc-9178ef2f1671` /
  `sha256:204b447e8fa0c68cb26e02d1e8697faebaeede47fe8028b67cb9190640aaee18`；最终 lifecycle
  binding rev4/epoch3 enabled/ready，3/3 live resources。

## 4/6 注册与九路 cutover

- registration Receipt `01b19d39-d2e1-4b67-b4a5-174ddbec5129`，request hash
  `sha256:769dbd7158a2e3358862bcbe9e24a3888daa6f88dbc98e1f77bdcd4f81b43568`，content hash
  `sha256:b676dc9ac29ec3ba12a60a92fbf871544b6dbbbac332f9f76307283b5813e42c`。
- cutover operation `335da3b8-6101-4f42-9235-0623b9dda80c`；prepare/pause/commit/validate/resume
  Receipts 依次为 `486ce27d-53cc-4ac3-b469-34d7f0217550`、
  `35f360b3-5411-4785-adfa-dd9922090442`、`651f5193-fcc9-4446-8142-49ecf3814924`、
  `227c680c-8be2-4eb8-92a6-7be0bd48fe79`、`b95ff350-9aa8-40c5-849d-c412d4d7f7b7`。
- 对应 content hash 依次为 `sha256:d0248f7931be00ebbba788d69d64efb15ccf9fc1cad12fb0c9bd8d8324bb1452`、
  `sha256:8af123dc0f0348f4e3a26acf5499e605a545c06c81248c7c2af78f8f309ed01b`、
  `sha256:77883a2f4a5d682854678efa3575c648ba991be74c9b2a7729cd036bdc7de99a`、
  `sha256:43bd7e1e772844ec1013c95941d5942cffbd71c1c965d85bf5bb5a641d0afc82`、
  `sha256:e5ff9646ac8cb2ace4f356b0b8d13764d7de21d5687b614317d858901fedb37b`。
- 最终 BY binding rev6/epoch3 enabled/unfenced/ready；九路 extension rev198/group225。

## 5/6 唯一 Host 与健康观察

- 唯一外置 Host PID 29455，状态文件 liveTargets 仅 BY；第二 Runtime Host=0、18181 listener=0、
  snapshot worker=0。
- 只读 repeatable-read 健康观察从 renewals=5 到 17、last sequence=18 到 30，target delta=12，
  35 samples；三资源始终 pending、未释放、未过期，最终 expires_at
  `2026-09-20T17:27:01.303854Z`。
- definition rev139 disabled；BY attempt=0；全局 running attempt=0、unresolved=0、runtime pending=0、
  canary=0。

## 6/6 验证与下一波

- snapshot members=12、running saved Run=12、Dataset Receipt=12；Store Receipt=0、`ecom_link`=0、
  projection pending=0。
- 新增逻辑仅为 BX 正式退休、BY 固定边界包装器与只读健康观察器，生产实现未修改；测试锁定 failed
  boundary、detach、lifecycle、registration、cutover 和 repeatable-read 观察，均禁止 `run_definition`。
- `py_compile`、完整约束测试与 `git diff --check` 作为提交前门禁。下一波自动执行 BY saved-snapshot
  recovery：保持 PID 29455 在线，证明第二 Host=0、18181=0、snapshot worker=0，再按纯 HTTP transfer
  rev140 / recovery46 / definition rev141 enabled、关端口后唯一自然 worker 与 terminal pause rev142 规则串行执行。
