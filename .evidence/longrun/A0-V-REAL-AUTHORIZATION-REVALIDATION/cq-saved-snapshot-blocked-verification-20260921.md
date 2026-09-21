# CQ 保存快照在配置刷新后门禁停止（2026-09-21）

## 结论

`CQ_SAVED_SNAPSHOT_BLOCKED_AT_J_BINDING_CONTRACT`。BudgetPolicy/RuntimePolicy 已正式续到
rev11；CQ 同 configuration family 已刷新到 rev2 且 Binding rev9/epoch5 enabled/ready。
随后 `prepare` 被既有 `current J binding differs` 合同拒绝，未生成 prepare 结果、未
transfer、attempt 仍为 0。按 AW 同一 fail-closed 分支转入 CQ blocked retirement 与 CR
direct successor。

## 证据

- Host PID 8784 保持唯一；18181 在 refresh 后已释放。
- text-readiness-v2 三例通过，ProviderCalls=3；renewal planHash
  `57bdebd9dec1405691d1d1f331cf49a24efcbd1a1c3a933dc86f05ba7b8423bf`，apply ProviderCalls=0。
- configuration rev2 hash `sha256:4fd728d8652c1be02b8300865283839c1cb4d86f0f2b6e120685a45c82fb632a`。
- 未执行 `extension_dispatch_configuration_refresh`；库内唯一 refresh receipt 仍属 J。
- 12 members、12 running Run、12 Dataset Receipt；Store/`ecom_link`/projection/canary=0。

## 下一波

CQ blocked retirement：source Binding rev9/epoch5、九路 252/279 epoch3、definition rev193
disabled、attempt=0。退休后以 exact detach Receipt 创建 CR successor。
