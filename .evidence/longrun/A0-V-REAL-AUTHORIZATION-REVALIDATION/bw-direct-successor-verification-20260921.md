# BV 正式退休与 BW direct successor verification（2026-09-21）

## 1. 结论

`BW_DIRECT_SUCCESSOR_GREEN`。本波按六步方案正式退休BV，并创建、启用、注册和切换BW；未读取商城
源数据，未创建业务attempt，未写负租户，未启动18181 API或snapshot worker，未手工调用
`run_definition`。

## 2. 方案执行与偏差

- HEAD基线 `8ff6fff6`；严格按plan、执行、verification、commit边界串行推进。
- BV唯一attempt `3afcfcae-b78c-4d15-8c64-4ec4e53325f3`已是failed rev4，原因
  `RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；definition rev133 disabled，未重发。
- 日期在本波开始时跨至2026-09-21，方案、幂等键和证据文件统一使用新日期；运行态UTC时间仍显示
  2026-09-20，属于同一Asia/Shanghai现场，不构成边界漂移。

## 3. BV正式退休

- BV installation/generation：`2b1aa826-b595-40d4-aeb2-9a7ce9d33c36` /
  `e8a5b32b-9a29-41bf-9c7f-87c7cd96b359`；原Host PID 15565一次SIGTERM后正常退出，读回binding
  rev7/epoch4 disabled/fenced/desired enabled与3/3 resources released。
- disable operation `abea8903-916f-4d60-ba24-3453aeb4e8a9`；fence Receipt
  `cbde9a98-7b32-4f6b-b87a-4bdaae0bcf78`，content hash
  `sha256:17e799a789b77a8f2a767ed158d2da968a0da6809beca31f755a2b76ee6f8149`。
- detach Receipt `76145710-3ec6-4271-a8b7-248e045645f7`，content hash
  `sha256:dc20911dba0fe1792b1a881f215109d8bf6f4db2754bdf12d3cc3fdab0e58608`。
- 最终BV binding rev9/epoch5 disabled/fenced/desired disabled；九路legacy rev191/group218。

## 4. BW lifecycle与cutover

- BW installation/generation：`9b6e1277-a0a2-447d-9062-a98adfed3f22` /
  `62cf014b-9ce5-4512-8a34-b55a79e053c3`；lock
  `sha256:5b2392496ba942a535260209dcf681030dd00b58765bf4983622d4af0be49ee0`。
- prepare/verify/configure/enable operation：`7ae84086-f149-44ac-969a-9fca54d17243`、
  `93285c41-dc33-4f95-a00f-adae876aa526`、`a4d93093-c6e1-4706-80d3-96550a04f31c`、
  `dadc0a75-c6c3-4bbe-b5be-b3ea4dbcd7c8`，均succeeded。
- configuration `99d47eef-7b92-4cf8-aa40-0f7056bbb9ca` /
  `sha256:27cf74ba5a8643ea91e31f1e540c18b12614df71dae98fd34ca5a39c51039b84`。
- registration Receipt `43e9f057-4f75-43c4-94f9-0ae52b49252a`，request hash
  `sha256:e470f616db8b9ad2a23595a90cf92a84f0ef7543139dd356543413695dcdc48d`，content hash
  `sha256:6537d72db6190e10f13c8253436c5e06868928c5e9baf47a2671e95e915949fe`。
- cutover operation `8fb2907d-0142-409d-b725-19aa53487f3d`；prepare/pause/commit/validate/resume
  Receipts依次为 `53543e25-35e4-49aa-ae84-f482af8ef3ab`、
  `95a442b8-73c8-42b7-a326-729db52ed5c0`、`b11151a8-b0fc-4a4c-9db9-34289dbb312b`、
  `dbf9bd4c-bae5-4cc4-82d4-35f50f1778a1`、`b108954e-97d1-4982-9510-e7c105097c9a`。
- 对应content hash依次为 `sha256:448822d7ba1b666ece94ec149e05aa5aa875747f127231f9937ad4639d3b3b7e`、
  `sha256:f238367b4070c4c44dec00760752ae8a674ddc389fb09df1d21bf4842a01faae`、
  `sha256:7451420ddd5ca3b1b22af410ef21a70230f5b3c715b7287b73714fe63814399e`、
  `sha256:e9c64804bc402d5ffddb16a48ce8148dba75ea16151198bc7faa395fd4572ab8`、
  `sha256:f7d5d9e71895f3bb8a2881f64fbc9d062bf38da26ba96df7691ff1765780a251`。
- 最终BW binding rev6/epoch3 enabled/unfenced/ready；九路extension rev192/group219。

## 5. 健康与零副作用

- 唯一外置Host PID 20193，状态文件liveTargets仅BW；第二Runtime Host=0、18181 listener=0、
  snapshot worker=0。
- 只读repeatable-read健康观察从renewals=5到17，target delta=12，37 samples；三资源始终pending、
  未释放、未过期，最终expires_at `2026-09-20T16:23:29.869751Z`。
- definition rev133 disabled；BW attempt=0；全局running attempt=0、unresolved=0、runtime pending=0、
  canary=0。
- snapshot members=12、running saved Run=12、Dataset Receipt=12；Store Receipt=0、
  `ecom_link=0`、projection pending=0。

## 6. 验证与下一波

- 新增逻辑仅为BV正式退休、BW固定边界包装器与只读健康观察器，生产实现未修改；测试锁定failed
  boundary、detach、lifecycle、registration、cutover和repeatable-read观察，均禁止 `run_definition`。
- `py_compile`与 `git diff --check` 通过；完整约束测试 `69 passed`。测试退出后的既有JDBC cleanup
  closed-stream日志仅为退出期告警，不影响pytest成功退出且不产生运行库写入。
- 下一波：先落 `BW saved-snapshot recovery` plan；保持当前唯一Host PID 20193在线，证明第二Host=0、
  18181=0、snapshot worker=0，再按纯HTTP transfer rev134 / recovery44 / definition rev135 enabled、
  关端口后自然worker与terminal pause rev136规则串行执行。
