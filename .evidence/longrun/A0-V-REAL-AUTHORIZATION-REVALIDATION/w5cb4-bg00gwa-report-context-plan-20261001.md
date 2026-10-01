# BG00GW-a 原 EvalRun/Report 上下文保真

基线 AOS-001064 / m1 825c7de4；Task W5CB4-BG00GWA-REPORT-CONTEXT-20261001。
承接 457/GW 审计，复用原 EvalReportRevision/EvalRunAuthorityRecord 五项可选字段；不改公共 schema、签名用途、许可、数据库 ACL 或阶段评测执行入口。

## 缺口与目标

原签名 writer 按包含 optional context 的 Report 计算并验证 contentHash，却在 INSERT 时遗漏 eval_contract_ref / subject_artifact_ref / stage_attempt_ref / gate_policy_ref / evidence_cutoff_at。返回 accepted 后回读不能重建原 hash。preflight 与 persisted reader 对 Run/Report 又只比较 Suite/Target/Dataset/Judge，未比较上述字段。
本切片完成判据：原 writer 对已具备其全部现行签名/来源条件的报告完整保存这些字段，读写两端拒绝与 Run 不一致的上下文。保持无 context 的旧报告兼容。不是新增阶段授权，不证明阶段正文受签名覆盖，也不允许绕过 generic runner 的 Skill 禁入。

## 文件计划及前 hash

- 新 aos_api/aip_eval_report_context.py：共享五字段一致性检查，JSON 严格区分 bool/int；cutoff 比较 aware datetime；不读库、不产生授权。
- aos_api/aip_eval_writer_atomic.py（c6bd9e65f1e9139107c81cdeb6bfbba68ec037822b1afdd3810d277a84dabaeb）：原事务 INSERT 保存四 JSON refs 与 cutoff。
- aos_api/aip_eval_writer_authority_preflight.py（bae4a59a47dd9aae87eea4c56ac3d3a9d78b4d2b1406e481fea014a22fa7df34）：原 Run 检查后调用共享一致性检查，拒绝发生在所有 INSERT 之前。
- aos_api/aip_eval_report_proof_reader.py（76fd9d29ae2dfc4d04c9fd56ea3d6b5dc675cafaeec290ca6fb37a0bad9bc0bf）：同一快照回读 Run/Report context 一致性。
- 新 tests/aip/test_aip_eval_report_context.py：类型/缺失/漂移反例；标准 disposable PG + 真实独立 NOINHERIT login + 真实测试密钥签名，原 writer 落库后原 reader 回读；试验 authority/Run/context 为具名测试来源，不伪称自然执行。

## RED、回归和边界

先复现 roundtrip hash 丢失及 Run/context 不一致仍被接受。专项验证 null/contract/stage metadata 形态、不完整绑定、严格 bool revision、时区、逐字段漂移和零部分 INSERT。邻接签名、连接、来源、回读测试；不得将旧 opt-in 跳过算通过，不并行 PG 测试。
本波不改 UI，无浏览器动作；只运行标准隔离测试数据库，硬校验 *_ti4_test 名称，当前真实数据库只读边界不变。测试权限仅在一次性库授予原 writer 角色，临时登录身份结束即撤销/删除，原集群角色不改。

## 风险和后续

此校验只证明 Report 与原 Run 元数据一致，不证明 Context 来自合法执行、也不证明正文被评测。原阶段来源验证、签名 inputHash 与原文本/合同的绑定问题仍需 GW-a 后续完整接线设计；GT 首次模型用途授权仍待裁决。禁止把此修复作为阶段评审/业务首链 GREEN。
失败时保留 RED 原因，逐点修复；回滚仅 revert 本切片文件，不动历史报告、不迁移当前库、不补录旧缺失数据。收口记录专项与累计实际输出、AOS/Prime、D-waves、精确 m1 提交。
