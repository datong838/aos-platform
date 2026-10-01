# Subject Report sidecar 隔离验证

基线 m1 3b1bd6c1 / AOS-001077；对应方案 `subject-report-sidecar-plan-20261002.md`。本波只增量建数据库证明关联，无当前实例迁移或自然业务写入。

## RED / GREEN

- RED：`services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_aip_eval_subject_report_sidecar_pg.py`，退出码 1：标准临时库仍为 a0v131，预期 a0v132；`aip_eval_subject_case_proof` 缺失。
- GREEN：`services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_aip_eval_subject_report_sidecar_pg.py services/aos-api/tests/aip/test_aip_eval_subject_persistence_pg.py services/aos-api/tests/aip/test_aip_eval_subject_persisted_reader_pg.py`，退出码 0，24 passed。
- 相邻：上述三项加 subject 签名/信封、旧 execution authority、Report context 与 Report proof reader，退出码 0，132 passed / 7 skipped。7 个旧 reader 测试依赖另一 opt-in 克隆库，未视作本次验证通过。

## 复审结论

`a0v_132` 仅新增复合唯一索引与 `aip_eval_subject_case_proof`：同租户/Run/Case/Envelope 复合 FK 精确绑定 source-witness、judge 的 Receipt ID 与 claim hash，再绑定同一 Run 的 EvalReport。临时 PG 正向行可读，错 Report、错 source/judge hash、错封套、跨租户无法插入；FORCE RLS、append-only、runtime SELECT-only。未改原 Skill sidecar、原 Eval Runner/reader 或普通运行 Gate。无前端变化，浏览器验收不适用。

风险：测试行是隔离约束 fixture，不是真实 Owner/Provider 事实。新表默认空，未授权任何运行角色 INSERT；真实 issuer、合法 EvalRun/Report 生产、writer 原子落库、阶段 reader 消费仍缺。当前真实库 a0v118、代码迁移头 a0v132，最新版本重启继续受独立安全迁移门限制。下一波须在原生成 Owner/当前安装 fence 上产生封套和签名，使用受限身份持久写入 Receipt+Report+sidecar，再让阶段消费同一快照重验；未知效果只读对账，不重发。
