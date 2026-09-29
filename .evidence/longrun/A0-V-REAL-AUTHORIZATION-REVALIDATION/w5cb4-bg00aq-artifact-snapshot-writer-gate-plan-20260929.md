# W5CB4 BG-00aq｜artifact_snapshot writer 当前元数据复验方案

## Rules 与上位约束

先读 AIP-4 Dataset/Store、BG-00ao/ap 方案与实现，再按 test-only RED→最小代码→专项/累计→verification。只改 `services/aos-api/aos_api/aip_eval_writer_authority_preflight.py` 和 test-only writer fixture/用例；当前库只读，不读商城源、不启 Host/worker/Provider。`artifact_snapshot` 只复用 Store 现有元数据语义；真实字节/正式脱敏签发及其他 source kind 不因此变 GREEN。

## 最小点

1. 在 BG-00ao 已校验 persisted Dataset manifest 后、任何 Receipt INSERT 前，用同一个 serializable 租户事务的 cursor 复用 `AipEvalAuthorityStore._assert_artifact_snapshot_source`。只对 `DatasetSourceKind.ARTIFACT_SNAPSHOT` 执行；Store 缺行/漂移异常归一为 `EvalExecutionRejected`，事务回滚。
2. test-only writer 只对 `aip_artifact` 增 SELECT 与租户 RLS 策略，不增 INSERT/UPDATE。fixture 由隔离 admin 注入精确 Artifact snapshot/Receipt 元数据与 sourceArtifactRef；先写缺行 RED，再核正向、坏 hash/链接/租户/空 ref 负向。清理策略/授权/测试行；当前正式实例不改角色或数据。
3. 专项与相邻回归、只读 DB/count/ACL 复核、方案一致性与风险复审。若 Store 方法直接 cursor 兼容性或隔离 ACL 不成立，停在 RED 并记录，不绕过权限。
