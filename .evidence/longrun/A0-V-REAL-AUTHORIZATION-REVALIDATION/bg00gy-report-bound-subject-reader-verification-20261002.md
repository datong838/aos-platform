# BG00GY｜Subject 持久双签与精确 Report 同快照读取 verification

基线 m1 `389dc3bd` / AOS-001079；计划 `bg00gy-report-bound-subject-reader-plan-20261002.md`。本波只改一个 reader 和它的临时 PG 测试，不改迁移、Stage command、旧 Skill Eval、Host/Provider 或当前真库。

| 门 | 本次命令/结果 |
|---|---|
| RED | `services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_aip_eval_subject_persisted_reader_pg.py -x --tb=short -p no:warnings`：valid case 因旧 reader 不接受 `expected_report_id` 报 `TypeError`，exit1。测试先于实现。 |
| 最小实现 | reader 新增必填 Report id/revision/hash，保持原 runtime tenant+repeatable-read/serializable 限制；同一 DB snapshot 连接 `aip_eval_subject_case_proof` 与指定 Report，核对 Run/Case/Envelope、双 Receipt ID+claim、Report suite/target/judge/contract/subject/stage/policy/cutoff/dataset、case passed/detail 和时间，再走既有撤销及 Ed25519 双签。 |
| 专项 | 同一个持久 reader 临时 PG：22 passed，负向包含缺 Report、缺 sidecar、错 Report/hash、case 结果、上下文和签发时序；exit0。 |
| 相邻 | 6个 Subject/旧 Skill writer 相关测试文件：**118 passed、3 skipped**，exit0。首次相邻回归为 6 failed/110 passed/3 skipped（共享 `_seed` 自动加 Report 导致原 sidecar 测试重复主键）；改为 reader 测试显式 `with_report=True`，原 sidecar 独立测试维持原行为后复跑 GREEN。3 skipped 来自旧 writer 专用配置，未计通过。 |
| 静态与变更范围 | `py_compile`、两文件 `git diff --check` exit0；未触碰用户已改的 browser plugin、pnpm lock、未知现场文件。无 Web UI 改动，浏览器不适用。 |

复审：新增函数只能返回双签结构声明及其与**调用者指定** Report 的持久绑定；它并未独立计算 Report canonical hash、证明 Report 是当前最新、读取原始 query/正文或安装 fence。调用者必须经原 `read_stage_eval_report` 与原生成 Owner 逐项验证，且正式 Subject producer/writer 缺失。因此本波不将 `gatePassed`、Subject 结构 pass 或测试签名晋升为阶段决策/首链 GREEN。当前权威库仍 `a0v_118`，代码头 `a0v_132`，最新版本全系统重启待独立门。

下一波直接沿 `ecommerce_analyst_{portrait,diagnosis,growth_plan}_receiver.py` 的原完成事件，追原 AgentRun/Artifact/Usage、安装 fence 与合法 EvalRun Owner；在独立配置与 PG 中实现受限 writer 的同事务 Report+sidecar，再让 Stage consumer 经同一稳定 snapshot 调本 reader。GT-a Model 首次评测用途仍是并列已批准代码项，不借 Subject 准入调用 Provider。
