# BW 正式退休与 BX direct successor verification（2026-09-21）

## 1/6 plan 与基线

`BX_DIRECT_SUCCESSOR_GREEN`。HEAD基线 `98bcb0c8`；BW唯一attempt
`4e3846d8-28b2-4c50-934b-8383df598956`为failed rev4，原因
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；definition rev136 disabled、recovery44。
本波未读取商城源数据，未创建业务attempt，未写负租户，未启动18181 API或snapshot worker，未调用
`run_definition`。

## 2/6 BW Host释放与正式退休

- BW installation/generation：`9b6e1277-a0a2-447d-9062-a98adfed3f22` /
  `62cf014b-9ce5-4512-8a34-b55a79e053c3`；原Host PID 20193一次SIGTERM后正常退出，读回binding
  rev7/epoch4 disabled/fenced/desired enabled与3/3 resources released。
- disable operation `08730e81-28b4-4931-9670-9056259a69ff`；fence Receipt
  `a31fd1ac-0e0f-43ae-ac0b-267cef96ff2c`，content hash
  `sha256:801ec2495052b354f9b81f3247fc12780bfbc3314138665ea69deb70d94a8326`。
- detach Receipt `d3ca6ecb-5fea-4dda-8a30-3ac9f5ce047c`，content hash
  `sha256:e1365bbc1f87d42997df4c04b5167d75895de232e69f81f9412e4ffaf9cebb5e`。
- 最终BW binding rev9/epoch5 disabled/fenced/desired disabled；九路legacy rev194/group221。

## 3/6 BX创建与 lifecycle

- BX installation/generation：`45db7b1e-6463-40f2-bf3c-c4e64ce3fd78` /
  `9beb5c99-aba7-4bec-9a10-4f98415aed2f`；lock
  `sha256:b4af00ba55283a22a08b1b045a3adc647854313856ebfd960bccff70f5a15152`。
- prepare/verify/configure/enable operation：`d3f509a2-0891-4348-b659-978694955721`、
  `ebc6810a-eb52-41c1-a023-af902d2b5155`、`259bddab-ece6-426b-bd96-bed71070ac9b`、
  `2ab06c7b-5316-491c-aa00-48412c30a86a`，均succeeded。
- configuration `a6ce6e53-6ef2-4e71-b5e1-87a37067ccd2` /
  `sha256:968820ac265ee07dec85fd5c4808351233b1175bf6d2e0be4307825a69212e97`；最终lifecycle
  wrapper沿用通用AV实现，部分中间展示字段outcome为空，但每步immutable result与数据库operation状态均已精确读回，
  不构成未知提交边界。

## 4/6 注册与九路cutover

- registration Receipt `733b5285-fdae-4e5d-b8a7-4dfd0ac6c463`，request hash
  `sha256:0ef5516f5c52725bd875a236fad852ecbbd0e5ee3866c19c23b64d7fe3edf130`，content hash
  `sha256:bdf14509b2641ea7b510e9b110d2c9838e3ef6261a1ed6bb737e4176190fdf18`。
- cutover operation `b3c173dc-ea28-41a8-b02c-702ac71ac456`；prepare/pause/commit/validate/resume
  Receipts依次为 `06181e12-bd11-4e40-9a2d-196e91aefd7c`、
  `40b96d7d-800d-4b73-a863-8b96c7a3f919`、`331e5a7a-8ef3-4999-8765-f849a4f98e78`、
  `b3754985-4ae7-404c-b662-6130f58350c2`、`9485c782-01c7-45bb-b9f9-33d3627a5c59`。
- 对应content hash依次为 `sha256:b64f8363903d9808b6be8c7c55b52cbeb57fdc530e5566f15ed5be19a9441666`、
  `sha256:9ee6bbecb5362c54bc9c4f6bcf0211869c0ce1ec892d465ccbfd4f531363f226`、
  `sha256:ea91cc1a3009207d1cafd3d4b98e9aabaf0c96c53ee8029559bf12019d557477`、
  `sha256:a86fbeae69ca66285b2e3587760ac05c046e90bc534a6353800d193a74be9063`、
  `sha256:b2e7b7e5380944d226e8630598ce6d24c35fc29e4eed4b8c7e594eeb21254f5c`。
- 最终BX binding rev6/epoch3 enabled/unfenced/ready；九路extension rev195/group222。

## 5/6 唯一Host与健康观察

- 唯一外置Host PID 26649，状态文件liveTargets仅BX；第二Runtime Host=0、18181 listener=0、
  snapshot worker=0。
- 只读repeatable-read健康观察从renewals=4到16，target delta=12，36 samples；三资源始终pending、
  未释放、未过期，最终expires_at `2026-09-20T16:56:29.961308Z`。
- definition rev136 disabled；BX attempt=0；全局running attempt=0、unresolved=0、runtime pending=0、
  canary=0。

## 6/6 验证与下一波

- snapshot members=12、running saved Run=12、Dataset Receipt=12；Store Receipt=0、`ecom_link`=0、
  projection pending=0。
- 新增逻辑仅为BW正式退休、BX固定边界包装器与只读健康观察器，生产实现未修改；测试锁定failed
  boundary、detach、lifecycle、registration、cutover和repeatable-read观察，均禁止 `run_definition`。
- `py_compile`、完整约束测试与 `git diff --check` 作为提交前门禁。下一波自动执行BX saved-snapshot
  recovery：保持PID 26649在线，证明第二Host=0、18181=0、snapshot worker=0，再按纯HTTP transfer
  rev137 / recovery45 / definition rev138 enabled、关端口后唯一自然worker与terminal pause rev139规则串行执行。
