# W5CB4 BG-00ao｜Eval writer 同事务 Dataset/Suite 来源绑定方案

## 上位复习与收窄

按 AIP-4 `aip_eval_dataset_revision`/`aip_eval_suite_revision`、Registry/Runner 合同和 BG-00an 审计，writer 不能只信 Run 自报的 suite/dataset JSON；必须在同一 serializable 事务读 exact persisted 版本。签名增长包 G2 placeholder 不是这两表的替代。当前正式表仍空、writer role0，本波仅 test-only 机制与失败关闭。

## 文件级计划

1. 修改 `services/aos-api/aos_api/aip_eval_writer_authority_preflight.py`：在任何 Receipt INSERT 前 SELECT 同 tenant `aip_eval_dataset_revision` 和 `aip_eval_suite_revision` 的 exact id/revision。Dataset 的 content/source/redaction policy/manifest source hash 和 case count 必须与 Report、Suite 一致；Suite 使用既有 `EvalSuiteRevision`/`compute_eval_suite_hash` 重算 canonical hash，并与 Run/Report 的 target/dataset/judge refs、case ID 集合和 gate threshold 对齐。`expected_input_hashes` 仍须独立提供且已由双签名绑定；Artifact 实际字节 hash/脱敏 Receipt 签发不在本波凭空证明。来源行缺失、错租户/版本/hash/case 一律拒绝。
2. 修改 test-only `services/aos-api/tests/aip/test_aip_eval_writer_atomic.py`、`test_aip_eval_writer_authority_preflight.py`、`test_aip_eval_writer_transaction.py` 和既有 `test_aip_eval_execution_authority.py`、`test_aip_eval_persisted_authority_reader.py`、`test_aip_eval_report_proof_reader.py` 的向后兼容签名/Report/Run fixture：先加 RED 证明没有 Dataset/Suite 时已有真签名路径仍提交；再让正向 fixture seed canonical test-only Dataset/Suite，并在最小授权中只增加两表 SELECT policy/GRANT，teardown 精确清理。保持独立非特权 LOGIN、错签/Report 冲突回滚及 current DB 零写。
3. 新增 `services/aos-api/tests/aip/test_aip_eval_writer_source_binding.py`：缺 Dataset/Suite、错 hash、Suite 缺 case、错 dataset ref/租户负例。专项/相邻累计、方案复审与 verification，m1 精确提交、316/D-wave/authority 更新。当前正式 G2 producer/Owner/S3/Host 继续禁入；后续再专门核 Artifact 字节/脱敏 Receipt 当前性。
