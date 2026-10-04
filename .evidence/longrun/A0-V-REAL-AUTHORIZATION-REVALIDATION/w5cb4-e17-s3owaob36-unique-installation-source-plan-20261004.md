# E17-s3o-w-ao-b36｜唯一当前安装的签名来源 Reader 施工计划

## 上位合同与当前证据

- 231-2/3/4、BIND-1：Capability Catalog published 只允许 provisioning；就绪、active 与每次调用必须以当前签名制品、当前安装代次、撤销和依赖在最终事务重验。b35 原包十项 hash 与 Catalog 逐项相同，但 b34 strict xfail 仍在，不能以 hash 重算授权。
- `CapabilityBindingRequest`/`OperationalBindingDependencies` 与原 Binding 表没有 Installation id。原 `current_installation_release_evidence` 只接受显式 Installation id，返回类型写明 `EVIDENCE_ONLY_NO_START`；单个 Binding 不足以猜测安装。
- 真实库只读 SQL 已见 Growth1.11.0 lock `contentHash=sha256:3d8817…02b328`；按 `org-org/dev-project` + bundle id/version + `active_revision=current_revision` + revision.state=`active` 选取得 0（当前仅 approved3/active NULL）。这与 UI 禁入一致，不是运行成功。

## 文件级最小步骤

1. 先在 `services/aos-api/tests/extension_runtime/test_current_installation_release_evidence.py` 增 Reader 负例：0 项、多项、错版本/hash、approved 未 active、跨租户均失败关闭；验证 SQL 同时约束 `i.current_revision=i.active_revision`、active revision 当前行、lock payload exact publisher/id/version/contentHash，`LIMIT 2` 检歧义。先跑 RED。
2. 在 `services/aos-api/aos_api/extension_runtime/current_installation_release_evidence.py` 增只读 `read_unique_active_installation_release_evidence`：一个只读 REPEATABLE READ 事务内找 exact 安装并调用原 `_read_exact_in_transaction`，重验 signature/Registry/lock/bytes；返回仍是 `EVIDENCE_ONLY_NO_START`。不碰原正向安装 API、不改 DB/schema、不可凭外层候选跨事务授许可。复用原 `apply_asset_transaction_scope`，低权矩阵另证；不盲查所有安装或仅凭 source_ref id/version。
3. b35 `inspect_current_capability_requests` 只在原 Loader 确认的签名目录上重算并对 Catalog hash；此 Reader 与 AIP readiness/activate/runtime 的接线必须有受限配置工厂和最终同事务复核。若当前调用边界无法安全复用原连接，保留 b34 strict xfail，拆下一精确波施工；绝不加假 `current=True`。普通 create→provisioning 保持。

## 验证与边界

- 专项/相邻：安装 Reader 单测、原签名/Registry/revocation 单测、AIP readiness；有条件的 full-schema test-only OCI 做签名 active 正向与错代/撤销/错 hash。当前权威库只读，迁移头135，原备份 b25 可恢复；Host/worker/Provider关。
- 后续若正式替换出现两个 exact active 安装，当前 Reader 拒绝歧义。只在产品/事务合同证明需要并存时再设计 additive Binding 安装锚点和 test-only 克隆迁移，不借现有用户可见目录猜测。每日提醒到达仍另执行最新完整 PG→API→Web 重启。`org-org/dev-project`唯一正向、`dev-org`零副作用，不读商城源、不回放旧12 Run、不手工 Run、不碰230 L0、不 push。
