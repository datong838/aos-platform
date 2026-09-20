# BS uncertain-resource 正式退休与 BT direct successor verification（2026-09-20）

## 1. 结论

`BT_DIRECT_SUCCESSOR_GREEN`。本波仅在 `org-org/dev-project` 内恢复BS唯一过期 uncertain
资源、正式退休BS并创建/启用/注册/切换BT；未读取商城源数据，未创建业务attempt，未写负租户，
未启动18181 API或snapshot worker，未手工调用 `run_definition`。

## 2. 重启恢复与方案偏差

- 重启后仅恢复既有 Colima profile 和 `aos-a0v-recovery-pg`；库内BS operation、binding、routes
  与HEAD `cd5b1dd2` 记录一致。
- 首次测试误用默认5433，连接拒绝且测试逻辑未执行；改用现有隔离测试端口18435后通过。
- 首次 cleanup preflight 因 `aos_runtime` 只读连接未建立租户作用域而受RLS隐藏，未执行资源恢复。
  方案与脚本先修正为 `consumer_connection(org-org/dev-project)` 后再执行。
- `ExpiredResourceRecovery.run_one` 为唯一资源写入 `resource_released` 事件并把operation从rev20
  推进到rev21；未沿用失效CAS。方案先更新为CAS rev21，再正式settle到failed rev22 /
  `PREPARED_RUNTIME_RELEASED`。
- 第一次Host启动使用了registration identity文件，被 `CREDENTIAL_FILE_INVALID` 安全拒绝；该进程
  未领取operation。随后使用既有三平面Runtime Host identity文件启动唯一Host，未重发prepare。

## 3. BS cleanup 与退休

- BS installation/generation：`c5a95204-c379-4763-b697-b4417349d204` /
  `6f8bcb56-5717-4d7a-9a9e-97c1982db053`。
- 唯一uncertain resource：`accb54dc-6341-4dc7-b8da-40202a102569`；恢复后3/3 resources均
  `released + observed_release=true`。
- 原runtime-apply `0587d5e6-1f14-4406-a1e4-95e8e556c583`：failed rev22，failure
  `PREPARED_RUNTIME_RELEASED`。
- disable operation：`0d5bbaa8-b5b4-4e12-b4cd-13b9ac00669f`，succeeded rev6；fence Receipt
  `755e4a56-07ed-4983-9eb1-ff26c0a6360b`，detach Receipt
  `ddd1e074-b90d-411e-93a3-0595d6e86d8b`，detach content hash
  `sha256:2995a8a4d8d2a74ddbde34a521de984af0afad13844303f6883befe48fe58242`。
- 最终BS binding rev9/epoch5 disabled/fenced/desired disabled；九路legacy rev182/group209。

## 4. BT lifecycle 与cutover

- BT installation/generation：`b05b7f06-67a0-4ea1-bc7c-1ba2108653d5` /
  `2c2d4cd5-d9bd-45b4-86d9-72a979eb0a58`；lock
  `sha256:053ba1e22ac7ddb9a0ff227643fe3bda76d37d8cc38e808df351954614edb974`。
- prepare/verify/configure/enable operation：`db62985a-616d-4dca-9a1b-44234d5e47f0`、
  `ffc64339-2978-46c6-9c4c-267a5aa0e53f`、`948413d3-03d1-40b0-ae66-6bcd76f0a9e3`、
  `402391c4-50d8-47cf-992f-494690860f72`，均succeeded。
- configuration `f4894956-2030-41a7-8794-32fbd458682a` /
  `sha256:1424de1b55ddc6105160570a813a81800acd3fbf11cdd83f55395730a8dba8cb`。
- registration Receipt `036755ad-fb38-470e-a341-212f4d76c5e9`，request hash
  `sha256:51a7cdd75454baa4dcef519a8ba713038fbd9cf2599f4da8a259c1ead9e23a8b`，content hash
  `sha256:6ce306796cb3b1e4f191ee11621f387141b798e8d7f05b2aa5856aac6d8a9b6b`。
- cutover operation `18eda226-e087-4342-bfc6-21def9226112`；prepare/pause/commit/validate/resume
  Receipts依次为 `2a8f6548-a70e-454d-971b-834417c64e04`、
  `63a5f3be-2d3f-4185-883a-85fc45bf0790`、`ca24219d-2ed2-4e25-b572-1613a5968ca9`、
  `e3935b46-0dc5-4ebb-941e-da07f4da375d`、`5f75cb32-65c6-48d8-b82c-a2c9cb207a26`。
- 最终BT binding rev6/epoch3 enabled/unfenced/ready；九路extension rev183/group210。

## 5. 健康与零副作用

- 唯一外置Host PID 4492；进程读回仅1个，故第二Runtime Host=0；18181 listener=0，
  snapshot worker=0。
- 只读健康观察从renewals=6到18，target delta=12，37 samples；三资源始终pending、未释放、
  未过期，最终expires_at `2026-09-20T14:39:08.260325Z`。
- definition rev127 disabled；BT attempt=0；全局running attempt=0、unresolved=0、runtime pending=0、
  canary=0。
- snapshot members=12、running saved Run=12、Dataset Receipt=12；Store Receipt=0、
  `ecom_link=0`、projection pending=0。

## 6. 验证与下一波

- `py_compile` 与 `git diff --check` 通过。
- 本波定向测试覆盖RLS scoped read、rev21→22 committed cleanup CAS、BS detach Receipt、BT lifecycle、
  registration、cutover与只读健康观察；完整结果 `49 passed`。
- 下一波：先落 `BT saved-snapshot recovery` plan；停止唯一Host并证明Host=0、18181=0、snapshot
  worker=0，再按纯HTTP transfer/recovery/definition enable与自然worker规则串行执行。
