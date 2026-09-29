# W5CB4 BG-00ac｜Skill Eval 原子边界只读结果

1. `aip_eval_runner.py:95-129,199-210` 对 `SKILL_TEMPLATE` 在 `run_by_contract` 与 `run` 两入口都明确抛 `formal Skill Eval executor authority unavailable`，既有 `test_aip_eval_runner.py:324,356` 覆盖禁入。因此不能用已存在的普通 Eval 运行结果冒充正式 Skill Eval。
2. `aip_eval_runner.py:225-309` 分别调用 `create_eval_run`、`transition_eval_run`、`_append_report`、末次 `transition_eval_run`；`aip_eval_authority_store.py:246-335` 的创建事务独立 commit，Report 见 `aip_eval_runner.py:339-385` 独立连接/commit。现有实现不是 Target/Judge Receipt + Report + 完成状态的单事务，直接移除 Skill guard 会产生半提交风险。
3. `aip_eval_contracts.py:435-444` 的 `EvalCaseResultEvidence` 只有 case/pass/hash/detail/duration，无 Target/Judge Receipt ID 或 claim hash；`aip4_003_eval_report_revision.py:21-51` 的 `results` 仅 JSONB 数组与总数约束；当前 Report 不能凭自身字段精确追溯双签名持久 Receipt。
4. `aip_eval_authority_store.py:469-520` 的通用 `require_exact_passed` 只核 Gate ref hash、passed、有效期及可选 target；`aip_skill_publication_service.py:119` 将其用于模型 route Gate，并非 G2 Skill case 证据消费。`rg 'read_persisted_execution_pair|verify_execution_pair|aip_eval_execution_receipt' services/aos-api/aos_api` 除 BG-00ab reader/纯验证器外没有生产接线。

结论：BG-00ab reader 是未接入的隔离只读机制；现有普通 runner 的多个 commit 点、Report 无双 Receipt 关联和 Gate 不回读这组证据，使“直接插一行校验并解除 Skill guard”不安全。下一波 BG-00ad 先文件级设计 Skill 专用 proof sidecar（每 case 精确双 Receipt/claim hash 与 Report 绑定）、独立单事务写入/读取接口，并在 test-only ACL 保真克隆里先 RED；新增表及当前迁移必须分波按一致备份、可恢复克隆、零执行窗口处理。正式 G2 issuer/Owner/内容、真实 S3 未就绪，生产 guard 不得解除。此审计没有运行或写入任何正式 Eval，也不证明自然首链。
