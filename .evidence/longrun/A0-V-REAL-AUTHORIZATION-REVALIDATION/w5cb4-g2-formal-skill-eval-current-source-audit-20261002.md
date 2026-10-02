# G2 正式 Skill Eval 当前来源与生产门只读审计

## 上位合同

复习 231 首链、228 G2 方案、D-waves BG00d/BG00ar 与 2026-10-02 原 Analysis 正链 RED。本轮不修改正式 Runner/Gate 守卫、不签发报告、不写当前库、不读商城源。

## 当前可复核事实

1. `test_product_event_analysis_bootstrap_pg.py -k formal_event_handle_creates_complete_initial_lineage` 在 `published_skill_runtime` setup exit1，`1 error`：`AipReleasePublicationService.derive_gate` 拒绝 Skill 目标 `formal Skill Eval executor authority unavailable`。原 Analysis handler 尚未运行，历史 `historical_event` seed 不算正式来源。
2. `AipEvalRunner.run`/`run_by_contract` 两个入口与 `AipReleasePublicationService.derive_gate`/Gate 复核均显式失败关闭。现有 `aip_eval_writer_atomic.persist_signed_skill_eval_report` 具独立 writer 身份/serializable/同事务双回执与 Report/Case proof 写入；`aip_eval_report_proof_reader.read_verified_skill_eval_report` 具逐 Case 当前签名核验。这些是正式持久化原语，尚未和 Runner→Gate 的当前原生产链连通。
3. 当前权威库 `aos_current_preview_20260927@a0v_135` 在 `BEGIN READ ONLY` 下，`org-org/dev-project` 的 `aip_eval_suite_revision`、`aip_eval_run`、`aip_eval_report_revision`、`aip_eval_issuer_root`、`aip_eval_executor_identity`、`aip_eval_execution_receipt`、`aip_eval_case_execution_proof` 七表逐项 0；无可供当前 G2 Skill Gate 使用的来源。未查询商城源。
4. 相邻 `test_aip_eval_writer_atomic.py`、`test_aip_eval_report_proof_reader.py`、`test_aip_eval_report_context.py` 合计 `12 passed, 10 skipped, 7 warnings`、exit0；跳过项显式要求 BG00AF/BG00AK 独立 PG URL，不把 12 passed 说成完整持久化正链。
5. `memoryctl sync --apply --prime` 输出的三项 `STALE` 是同步前差异；随后 `memoryctl sync --json` 对 `AOS-001152` 回 `changed=0, changes=[]`，Prime 投影已对齐。此前将前一次 apply 输出直接表述为仍 STALE 不准确。

## 下一安全步骤

先按 BG00d/ar 冻结首链必要 exact Skill r1、真实 Dataset source/Case Artifact、受控 Target/Judge 与脱敏签发 Owner、独立 writer/issuer 身份和费用。文件级 RED 应在可销毁 PG 使用原签名 producer→完整逐 Case proof reader→Gate→PublicationEvent，并覆盖撤销、错租户、错版本、缺 Case、过期与幂等；只有证明该链，才有条件分别替换 Runner 和 Gate 的显式禁入。当前配置/身份材料缺失时只阻断当前实例，继续可独立的合同和失败封闭代码。不得将测试 fixture、历史报告或本机预览签名升格正式来源。
