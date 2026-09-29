# W5CB4 BG-00aq｜artifact_snapshot writer 当前元数据门验证

方案：`w5cb4-bg00aq-artifact-snapshot-writer-gate-plan-20260929.md`。仅改 writer preflight、test-only fixture 与新专项测试；Store 原元数据规则复用，非 artifact 来源行为不变。当前库只读。

## RED/GREEN

- RED：test-only `aos_bg00ad_schema_v2_20260929@a0v_114` 下，`artifact_snapshot` Dataset 已登记而 Artifact 两行缺失，原 writer 仍提交：`pytest -q .../test_aip_eval_writer_artifact_source.py -x` 退出1，`Failed: DID NOT RAISE EvalExecutionRejected`。这证明 BG-00ao 的持久 Dataset 门未覆盖当前 Artifact 元数据。
- 最小实现：BG-00ao manifest 检查之后、任何 INSERT 之前，仅 `DatasetSourceKind.ARTIFACT_SNAPSHOT` 调用 Store `_assert_artifact_snapshot_source`，使用 writer 的同一个 serializable 租户 cursor；Store 缺失/冲突异常转 `EvalExecutionRejected`。test-only 对 `aip_artifact` 临时授 SELECT + 精确 tenant RLS，不授写权限。
- 初次 GREEN 遇 test-only `aip_artifact` append-only 清理触发器，退出1 `AIP4_APPEND_ONLY`；修复 fixture 在单个清理事务中临时禁用/恢复 USER trigger，只删除 `created_by='bg00aq-test'` 的本波两行，并撤销临时 policy/SELECT/login。失败测试留下的 test-only 行/策略/登录已精确手工清理，退出0。
- 最终专项 `5 passed`，退出0；含缺 Artifact、坏 source hash、坏 redaction 链接、空 content_ref 四负向，精确 metadata 真签名正向。BG-00ao/ak/aj/al 及签名、sidecar、迁移/HTTP 相邻累计 `80 passed`，退出0。`git diff --check`、三文件 `compileall -q` 退出0。

## 当前读回与风险

- test-only 和当前 `aos_current_preview_20260927` 只读查询均 `alembic_version=a0v_114`，Dataset/Suite/Run/Receipt/Report/sidecar 六表逐表0；test-only 本波 Artifact 行/policy/login各0。API `/v1/health`、`/v1/ready` 与 Web `/aip/skill-publish` 均 HTTP200，18181 LISTEN 0。
- 元数据门只适用于 `artifact_snapshot`，不读对象字节，也不核正式脱敏签发或撤销；`selection_snapshot` 等来源仍需 Owner 决定允许范围与独立证明。正式 Eval writer role/credential、G2 producer/Owner/S3、Host/自然首链当前均缺。不能把此测试当业务闭环。

## 下波

BG-00ar 先只读审查正式来源允许列表、G2 placeholder 与已实现的 S3 有界读回器/撤销合同，确定能独立加的同事务权限门；不以测试对象替代生产对象。
