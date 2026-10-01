# Subject Report 精确侧证绑定波开工卡

所属业务结果：231 的首条“真实产物→评审→自动续跑”；本波仅补签名证明与不可变 EvalReport 的数据库级绑定，非业务验收。基线 m1 `3b1bd6c1` / AOS-001077，代码迁移头 a0v131、当前真实库 a0v118。用户已授权 subject-review 代码/隔离验证，未授权真实库迁移或自然运行。Rules：AGENTS、aos-engineering-delivery、m1 单写、方案先行、RED、最小 additive 迁移。

进入事实：原 `a0v_114` 将 Skill target/judge 收据经 `aip_eval_case_execution_proof` 精确 FK 到 Report；新 `a0v_131` 仅将 source-witness/judge Receipt 绑定 EvalRun/Case/Envelope。`ecommerce_analyst_stage_review_command.py` 已在事务内读生成 AgentRun、query/正文和 Report，但尚未读新双签；原 Runner 在 Skill Run 创建前禁入。缺少 Report sidecar 时不能证明当前 Report 的结果对应同一封套。

验收动作 ID：SUBJECT-REPORT-FK-01。精确文件与前 hash：`alembic/versions/a0v_131_subject_review_persistence.py`=`772dcdd4...`（只读）；`a0v_114_skill_eval_case_proof_sidecar.py`=`a8eb0977...`（只读）；`tests/aip/test_aip_eval_subject_persistence_pg.py`=`f28c909f...`（只更新 head 断言）。新增 `services/aos-api/alembic/versions/a0v_132_subject_report_case_proof.py` 和 `services/aos-api/tests/aip/test_aip_eval_subject_report_sidecar_pg.py`。

输入输出合同：增加 `aip_eval_subject_receipt` 的 exact composite 唯一键；新增 `aip_eval_subject_case_proof`，同租户/Run/Case/Envelope/Report 唯一，source-witness 与 judge 的 receipt ID+claim hash 各以复合 FK 引用同一封套的不可变行，并以 FK 引用同一 Run 的 Report。`verified_at<=created_at`、严格 purpose/64位摘要、append-only、FORCE RLS；普通 runtime 仅 SELECT，PUBLIC 零权限，本波不授 INSERT。不得改旧 Skill sidecar 或把签名/Report 关联自动解释为 Gate 通过。

RED：标准临时 PG 的 a0v131 无表/无 FK 测试失败；GREEN：迁移至唯一 head a0v132，真实约束接受同 Report 双签组合，缺 Report/错 hash/错封套/跨租户失败；runtime 只读、RLS、不可变。相邻 subject reader、旧 Skill proof、迁移验证回归。临时 seed 为约束测试，不是原 Owner 生产事实。无 Provider/Secret/当前库写入，浏览器不适用。

风险与回滚：迁移只新增索引/表，downgrade 禁止静默删除证明。代码头会领先当前库更多一版；当前实例仍按独立备份、克隆、零执行窗口与正式身份门处理。下一 Task：复查合法 EvalRun/Report Owner 与生成来源，设计受限 writer 原子插入 Receipt+sidecar+Report，后接阶段消费者；所有来源缺失保持实例禁入，不阻断整个 Goal。
