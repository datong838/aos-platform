# W5CB4 BG-00ap｜Dataset Artifact/脱敏 Receipt 当前来源只读审查

方案：`w5cb4-bg00ap-artifact-redaction-source-audit-plan-20260929.md`。复习 BG-00k/n/o 与 AIP-4 Store/Manifest/Object reader 后得到以下边界：

1. `AipEvalAuthorityStore.create_dataset_revision` 仅当 `EvalDatasetManifest.source_kind=artifact_snapshot` 时，写前在同一 Store 事务调用 `_assert_artifact_snapshot_source`：按 tenant 查 `aip_artifact` 的 `eval_dataset_snapshot` 与 `redaction_receipt`，核 exact hash、非空 `content_ref`，及脱敏 Receipt 的 `sourceArtifactRef`。`selection_snapshot` 等来源不走这条专用分支。BG-00ao writer 当前只核持久 Dataset manifest 与 Suite，不复验上述 Artifact 当前 metadata；test-only 正向为 `selection_snapshot`，不能被说成正式 G2 来源。
2. `aip_eval_object_reader.read_verified_eval_object` 已实现 tenant eval key、2 MiB 有界 GET、SHA256 字节门，但未接 Dataset Store/Writer。BG-00o 两次固定 `minio/minio:RELEASE.2025-04-22T22-12-26Z` 下载均因 Docker Hub TCP 超时失败，真实 PUT/GET 未跑。本波再查固定 image inspect 退出1、19000 `lsof` 退出1，现仍无 MinIO 可用服务。
3. 当前 `aos_current_preview_20260927@a0v114` 以 READ ONLY SQL 查询：`org-org/dev-project` 和 `dev-org/dev-project` 的 `aip_artifact` 中 `eval_dataset_snapshot`/`redaction_receipt` 均0，Dataset/Suite 各0；`aos_runtime` 对 `aip_artifact` 有 SELECT，但正式 Eval writer role 仍不存在。签名增长包 G2 Eval placeholder 仍 BLOCKED；未读取商城源、对象字节或凭据。

判定：当前正式 G2 producer/脱敏签发/对象存储 authority 不存在，不能把 test-only selection manifest 或 metadata 行当业务真源。下一波 BG-00aq 可独立复用现有 Store 的 `_assert_artifact_snapshot_source` 只读逻辑，在 writer 同一事务对 **artifact_snapshot 分支**做当前 metadata 复验并 test-only RED；不得因此把其他 `source_kind` 自动判 GREEN。之后需正式 Owner 冻结允许的 G2 source kinds、内容格式/allowlist/case count、脱敏 Receipt 签发与撤销、真实 S3 字节回环，再决定统一来源门。当前 Host/worker/Provider 继续禁入。
