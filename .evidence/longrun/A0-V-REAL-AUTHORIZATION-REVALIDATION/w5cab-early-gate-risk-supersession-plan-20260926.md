# W5cab｜早期 24h/Owner/Host/Store 当前风险去过期项方案

## 上位与当前门

复习 231 A0-V→A1、230 L0 挂起、W5c4x/y/z 和 W5c5a–W5c6n 已提交 verification、W5ca4 的 `ELIGIBLE_NO_AUTHORITY`、W5ca5 的 Owner SQL 审计、W5ca8 当前风险尾段清理。AOS-000725 的 `incomplete` 前段仍有“严格 24h pending、成功/回放未测试、隔离 Store 无 Host lease API”等旧时间点语句。它们误导接力，但真实 Fleet/Owner/历史行/真库迁移并未因此变绿。

## 文件级最小清单

- 只读：`docs/palantier/AOS项目开发上下文/memory/authority.json` 的 `incomplete` 前段、W5c4x/y/z、W5c5a–z、W5c6b/e/n、W5ca4/5 verification；核 `m1` 提交和现场 18181/8080 只读状态。
- audit 建立精确“旧条目→后继证据→仍保留的真实风险”矩阵。只移除可被后继验证直接反证、且被新的风险条目覆盖的旧描述；原十二 Run running、旧库迁移未部署、全机 Fleet/Host、Store effect 分事务、真实业务回执 0、历史独立原始行、实际租约到期未证必须保留。不概括删除整段。
- 仅通过 `scripts/memory/memoryctl.py authority-update` expected-revision CAS 替换完整 `incomplete` 数组；自动投影 `docs/palantier/AOS项目开发上下文/memory/{authority.json,events/2026-09-26.jsonl,projections/aos-project.json}`、`01-当前项目状态.md`、`06-当前执行检查点.md`；补 D-waves、上下文 157、Prime。生产代码/DB/Host 不变。
- `memory-validate` GREEN、Prime CURRENT；JSON 断言硬门完整，历史 verification/events 不删；若证据不能直接覆盖，则保留，CAS 漂移 STOP。

## 九步

1. 上位复习；2. 本方案先提交；3. 逐条审计；4. 最小 CAS；5. JSON/投影校验；6. 8080 离线、18181 文档只读；7. 风险/方案一致性；8. verification/D-waves/上下文/Prime/精确提交；9. 自动下一波。

不得重发旧 attempt、手工 run_definition、调用原组 closure/ACK/商城源，230 L0 挂起，dev-org 零 canary，m1 单写不 push。
