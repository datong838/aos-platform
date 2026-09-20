# BN canonical alias 修复、BM 退休与 direct successor 验证（2026-09-20）

## 1. 结论

`BN_DIRECT_SUCCESSOR_ACTIVE_SINGLE_HOST`。BM 因非生产 artifact alias 失败后已正式退休；
四个新不可变 `.2` 坐标全部使用 `bundle://a0v-canonical/...`，生产
`ManifestLoader` 验证通过。BN 已从精确 BL detach authority 创建、激活并完成九路切换，
当前为唯一 active successor。全程未读取商城源数据、未手工运行 definition、未产生业务
attempt、Store Receipt、ecom_link 或 projection pending，负租户 canary 为 0。

## 2. Registry 与 artifact

- build/qualification：`BUILD_GREEN` / `QUALIFICATION_GREEN`，相同 output tree
  `sha256:6e704c753aa8f4bc3611e957af97c03eedb49d1c89a5910a91cad9c986b7ba2c`；
  三个 runtime session 各完成 2048 次 heartbeat check 后 released，tamper 7/7 拒绝。
- 发布前后：versions `23 -> 27`、targets `0 -> 4`、installations 保持 74、canary 0；
  source read / provider / external publication / installation mutation 均为 0。
- 新坐标与内容哈希：
  - `domain.ecommerce.core@1.4.2`：`sha256:dd03a29a71b7cc8f35a36010042f8f6d7bd0d19dcde1ac107c7c588f2337d441`；
  - `platform.ecommerce.niushop@1.23.2`：`sha256:052214c06f08bd930daea552f7ade0ee49313abde9e3292fdaa8d071d41a8c90`；
  - `solution.ecommerce.growth@1.10.2`：`sha256:85ca84cb835758d40877a81510865ff6c958cc6933fdc689bf3d77a4f3bd74a6`；
  - `solution.ecommerce.operations-base@1.2.2`：`sha256:ca0f6e74bcb428efd78c868285cd9fbed136919d4676b46aee9e181e8eec33ec`。
- production artifact proof 为 `BN_CANONICAL_ALIAS_ARTIFACT_PROOF_GREEN`；三个 runtime
  index digest 分别为 `sha256:7eb64fb6...`、`sha256:1539aeca...`、
  `sha256:e12cbf98...`，四个 source ref 均为精确 canonical alias。

## 3. BM 正式退休

- installation `370d4287-3402-40bb-b3da-d479633da7c4` 从 approved rev3/etag3
  转为 uninstalled rev4/etag4。
- 前置读回：binding 0、未终态 operation 0、未释放资源 0、canary 0；首次 uninstall
  `replayed=false`，同 key 读回 `replayed=true`。
- 退休原因固定为 terminal runtime artifact alias rejection；business operation 与 provider
  invocation 均为 0。

## 4. BN 创建、激活与切换

- installation `d89bca67-4472-4b43-b0bd-ae8a2e0459f5`；generation
  `a43b3e64-7bb4-454c-822e-58bc13acbcaa`；composition
  `c0b6042c-62ab-4266-87a9-1f9b5cc3c8af`；lock
  `sha256:d0f24b0d57a20c0c2606609794c386471484711d823f63c05752db160ea09d9b`。
- configuration `ddfb0b72-f106-4136-8222-41cf04349724` rev1，hash
  `sha256:b36ad7ae5f4c6f3b05e3fcb971ca0b533ae1f6fdf36e5b959d9d49ae5b4de910`。
- runtime-apply `4d4a686f...`、verify `8e81cf13...`、configure `55232be7...`、
  enable `4a4f51c3...` 均正式 succeeded；最终 binding rev6/epoch3，enabled/ready，
  operation fence=false，三资源 pending/live。
- successor registration receipt `b9bd87b5-c934-4769-a644-371f6db9922f`，请求 hash
  `sha256:52ce21b8278a1ec08bb104fe5ff8f914784dc5aeb0062e5d7860437d27bb9c5e`。
  重启后历史 registration identity 丢失导致首次调用在事务前失败；数据库确认 receipt=0
  后，轮换既有独立最小权限角色密码并以相同 frozen intent 收敛。角色仍 NOINHERIT、无高权，
  可达角色精确为 runtime 与 maintainer 且无 admin option。
- cutover operation `dda42306-073e-4d30-9027-680510925b05` 严格按
  approve -> prepare -> pause -> commit -> validate -> resume；最终九路均为 extension
  rev165/group192、BN generation/epoch3、fence=false，claim 恢复，无 rollback。

## 5. 健康与零副作用

- 一个且仅一个 Runtime Host（PID 58971）；18181 未监听；第二 Host=0。
- 健康观察 baseline 15 -> final 27，delta 12，31 个样本；最终 last sequence 40。
- definition `cb0dba8c-803f-5caf-8011-b763d349f2ba` 为 rev118 disabled。
- BN attempt=0、tenant running=0、claimed/unknown=0、runtime pending=0、canary=0。
- snapshot group 保持 members=12、saved runs running=12、dataset receipts=12；
  Store Receipt=0、ecom_link=0、projection pending=0。
- 最终 observe：BN active/binding ready；BL 保持 exact detached predecessor；没有商城源读取。

## 6. 自测、风险与下一波

- `test_a0v_bn_canonical_alias_repair.py`：7 passed。
- 已检查实现与本方案一致：未知边界先只读对账；没有 `run_definition`；没有扩大 alias
  allowlist；无关工作区修改未纳入本波。
- 已知非业务风险：首个 300 秒健康观察预算不足，在 delta=5 时只读超时；随后同 baseline
  的 960 秒观察器连续覆盖并达到 delta=12，未产生状态写入。
- 下一波：`BN saved-snapshot recovery`。先关闭 Runtime Host，纯 HTTP 18181 启动并读回
  Cron=false、snapshot worker=false、第二 Runtime Host=0；再执行 transfer -> recovery ->
  definition enable，关闭端口后仅起自然 worker，单轮 50 秒只读采样唯一 attempt 至正式终态。
  若 300 秒为 `RECOVERABLE_INGRESS_DEADLINE_EXCEEDED` 且十二 Run/零副作用边界保持，按
  既定第 6 步进入 1800 秒有界预算，不在 BN 内手工重发。
