# CA 正式退休与 CB direct successor verification（2026-09-21）

## 1/6 plan 与基线

`CB_DIRECT_SUCCESSOR_GREEN`。HEAD 基线 `b02a3da1`；CA 唯一 attempt
`4a3ca4e5-db9f-47a0-a283-2adf23d25e84` 为 failed rev4，原因
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；definition rev148 disabled、recovery48。
本波未读取商城源数据，未创建业务 attempt，未写负租户，未启动 18181 API 或 snapshot worker，未调用
`run_definition`。

## 2/6 CA Host 释放与正式退休

- CA installation/generation：`0d834ab1-fd2b-4dbc-b9a5-0f0dee712647` /
  `1f18a077-12c6-4242-982a-0c3fa1159540`；原 Host PID 34620 一次 SIGTERM 后正常退出，读回 binding
  rev7/epoch4 disabled/fenced/desired enabled 与 3/3 resources released。
- disable operation `077c473a-dd7c-463b-87d3-eafb228cfbc5`；fence Receipt
  `ae96f298-ac95-4be5-91ac-8724dea275b7`，content hash
  `sha256:4922870e5c4a46eb0c5dddec9be0ae5fc3e6b0f62fd99dc41477da30420ecca3`。
- detach Receipt `bfffc7e7-5606-4101-9b5e-bc729ddb26ef`，content hash
  `sha256:f4178b7c27dc9addc0fe17a13f446302af66d291960cd1c7a8aae6aab98554ce`。
- 最终 CA binding rev9/epoch5 disabled/fenced/desired disabled；九路 legacy rev206/group233。
  这里的 group233 仅为 cutover group revision，230 L0 仍保持挂起。

## 3/6 CB 创建与 lifecycle

- CB installation/generation：`3d6df614-5a05-4c6f-823e-688d81e84096` /
  `0cceac8c-c831-4b3f-92c3-fc35240c5414`；lock
  `sha256:658b48f2444dfd18c6c42bbbadd22a7952063c60b6bae95d7384c6841ab9d3f7`。
- prepare/verify/configure/enable operation：`c2645b92-40b0-41e4-a383-d76bdc772017`、
  `599c98b2-5959-4934-ae36-255b275e012a`、`eed8cc4d-1495-4799-89f3-5730e8688460`、
  `3b0683ec-2405-495e-972c-46daa115e071`，均 succeeded。
- configuration `76a01ce7-4c6c-406e-bc4e-a52cd957240c` /
  `sha256:aa4cf1ee80739db6f487f95ac2226e18b7bf1d8cb709082303e078ae6c3c81a7`；最终 lifecycle
  binding rev4/epoch3 enabled/ready，3/3 live resources。

## 4/6 注册与九路 cutover

- registration Receipt `4223dce3-e34e-40c9-8702-d9d21a673230`，request hash
  `sha256:9a8e8bdeeac4af3bb39c9205b5aaa8856e6796ade28cc4907621af09ab9778e0`，content hash
  `sha256:68af281e1fe64732c929faf118ef052bbab991c3caed517b648ed30b76286d36`。
- cutover operation `8da61041-939b-4cb9-a1e9-fbc8ac87effd`；prepare/pause/commit/validate/resume
  Receipts 依次为 `b01d1f38-33a6-440a-bd39-28a7c585dc27`、
  `5e2216f4-f4e7-45c8-b3de-19f7f6c5af4b`、`9a98607d-38b8-49c9-b564-60e138da6678`、
  `31e675ec-b5ea-473c-83dd-cf2710547d63`、`4af4965f-9ebf-4152-8982-b264268f76e6`。
- 对应 content hash 依次为 `sha256:a9df05d52988713c6395a69f8294b80f3e834a4715c46bd1f6e5f591796aa347`、
  `sha256:168f8abb2fab1896089ae6a5eb5dbd0ce005f603f42e975892dcad443f6e1f0b`、
  `sha256:96ad2f39f5f4e4e78be0e74560528d19077143acb90475b1be6cf11c22756d57`、
  `sha256:ad44a77ba2a6904b8396e378f08d390d1fc1ac1c0122c37d28eb46853f9bc27b`、
  `sha256:3dd1cb8072054d4acf99cd41ec1d6cc2c93eb0fb2dadfb22e8fe5a766c313a1b`。
- 最终 CB binding rev6/epoch3 enabled/unfenced/ready；九路 extension rev207/group234。

## 5/6 唯一 Host 与健康观察

- 唯一外置 Host PID 36215，状态文件 liveTargets 仅 CB；第二 Runtime Host=0、18181 listener=0、
  snapshot worker=0。
- 只读 repeatable-read 健康观察从 renewals=4 到 16、last sequence=17 到 29，target delta=12，
  37 samples；三资源始终 pending、未释放、未过期，最终 expires_at
  `2026-09-20T18:50:03.422154Z`。
- definition rev148 disabled；CB attempt=0；全局 running attempt=0、unresolved=0、runtime pending=0、
  canary=0。

## 6/6 验证与下一波

- snapshot members=12、running saved Run=12、Dataset Receipt=12；Store Receipt=0、`ecom_link`=0、
  projection pending=0。
- 新增逻辑仅为 CA 正式退休、CB 固定边界包装器与只读健康观察器，生产实现未修改；测试锁定 failed
  boundary、detach、lifecycle、registration、cutover 和 repeatable-read 观察，均禁止 `run_definition`。
- `py_compile`、完整约束测试与 `git diff --check` 作为提交前门禁。下一波自动执行 CB saved-snapshot
  recovery：保持 PID 36215 在线，证明第二 Host=0、18181=0、snapshot worker=0，再按纯 HTTP transfer
  rev149 / recovery49 / definition rev150 enabled、关端口后唯一自然 worker 与 terminal pause rev151 规则串行执行。
