# BT 正式退休与 BU direct successor verification（2026-09-20）

## 1. 结论

`BU_DIRECT_SUCCESSOR_GREEN`。本波在 `org-org/dev-project` 内正式退休已释放资源的BT，并创建、
启用、注册和切换BU；未读取商城源数据，未创建业务attempt，未写负租户，未启动18181 API或
snapshot worker，未手工调用 `run_definition`。

## 2. 方案执行与偏差

- HEAD基线 `f5ce9d56`；按先方案、后执行、再verification的六步顺序推进。
- BT在上一波安全停机后已是binding rev7/epoch4 disabled/fenced/desired enabled、3/3 resources
  released；本波没有原地复活BT，而是走正式退休和direct successor。
- 重启后的默认测试端口5433未恢复，首次纯源码约束测试在fixture建库前连接拒绝，测试逻辑未执行；
  随后以既有共享库测试开关只执行纯源码约束测试，并通过容器内权威库独立完成只读运行核验。
- 健康观察开始前主机侧窄过滤未匹配实际脚本名；状态文件与PID精确读回确认唯一Host PID 10997
  仍在线且liveTargets仅BU，因此未启动第二实例。

## 3. BT正式退休

- BT installation/generation：`b05b7f06-67a0-4ea1-bc7c-1ba2108653d5` /
  `2c2d4cd5-d9bd-45b4-86d9-72a979eb0a58`；退休前3/3 resources均released。
- disable operation `84699050-9e0a-48b7-8dc3-99e2d7dbc669`；fence Receipt
  `fcbeed60-381d-419f-9180-9a9182e524fd`，content hash
  `sha256:a1e4a384a43a28eff93aa08f43578a4257aedc76707ac6731d2ba1fe8b2406a5`。
- detach Receipt `3c4c44d3-7f5f-4829-951a-5ba5c4c37aaa`，content hash
  `sha256:49271deaba3745fe1f75f7e041b058f285f6706364cda4d8afddb0315b9c5528`。
- 最终BT binding rev9/epoch5 disabled/fenced/desired disabled；九路legacy rev185/group212。

## 4. BU lifecycle与cutover

- BU installation/generation：`d1dcf5c2-f6ff-48b2-b6f1-fb05d17b7895` /
  `cb8ace71-ba8d-4e08-816b-8d6bbc0f0281`；lock
  `sha256:470af8d75bc784496260df85be7953537f2d2ead135167dc2d14f16e9bc1d2ed`。
- prepare/verify/configure/enable operation：`a36f4a07-d71b-4f8b-bf12-5569a5c08fba`、
  `6a46af0c-28f5-42da-9448-d99f6fa25d49`、`abd1ee47-c41b-4a01-883c-5c9a33d0ff1d`、
  `1a3ea654-6347-4863-beb4-95379f725b2e`，均succeeded。
- configuration `15ceb457-eb93-492e-bc63-54438d198b44` /
  `sha256:7f5d97cf81ff96988eabae4161448ef8bfe830b6c91a145dd2e5d5e33e642a22`。
- registration Receipt `22e74533-d6bb-4adf-b6de-940151620469`，request hash
  `sha256:cbdde55e9549ebfc8367fecc483ff734a04d61f53e48cb5f7e6b544291dc3867`，content hash
  `sha256:2e31b2e66d14289ddfd8f995282c344c6293c7ae18d8f3c970fbfed090a09cb2`。
- cutover operation `ec731e19-1161-451c-8585-9c59849ea6c0`；prepare/pause/commit/validate/resume
  Receipts依次为 `8e45f234-f00c-4ece-a44e-119059c27ee0`、
  `111cd9f7-e2ca-4e49-9d5a-1fe05696d51c`、`ece8390b-aa51-4ab4-a86d-2dfd723306c2`、
  `e2ba3c2e-3fa3-4cfb-9668-18ad6277e962`、`6e9882cd-d887-4d19-b06e-cb613a97d49c`。
- 最终BU binding rev6/epoch3 enabled/unfenced/ready；九路extension rev186/group213。

## 5. 健康与零副作用

- 唯一外置Host PID 10997，状态文件liveTargets仅BU；第二Runtime Host=0、18181 listener=0、
  snapshot worker=0。
- 只读健康观察从renewals=6到18，target delta=12，34 samples；三资源始终pending、未释放、
  未过期，最终expires_at `2026-09-20T15:12:18.330879Z`。
- definition rev127 disabled；BU attempt=0；全局running attempt=0、unresolved=0、runtime pending=0、
  canary=0。
- snapshot members=12、running saved Run=12、Dataset Receipt=12；Store Receipt=0、
  `ecom_link=0`、projection pending=0。

## 6. 验证与下一波

- 新增逻辑仅为BU固定边界包装器与只读健康观察器，生产实现未修改；约束测试锁定BT detach、BU
  lifecycle、registration、cutover和repeatable-read健康观察，不包含 `run_definition`。
- `py_compile` 与 `git diff --check` 通过；完整约束测试结果 `53 passed`。测试退出后的既有JDBC
  cleanup logger出现closed-stream告警，不影响pytest成功退出且未产生运行库写入。
- 下一波：先落 `BU saved-snapshot recovery` plan；保持当前唯一Host在线，证明第二Host=0、18181=0、
  snapshot worker=0，再按纯HTTP transfer/recovery/definition enable与自然worker规则串行执行。
