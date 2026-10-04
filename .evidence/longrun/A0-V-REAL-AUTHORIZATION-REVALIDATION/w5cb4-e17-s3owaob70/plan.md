# b70 并发撤销文件级方案（准备完成，RED尚未执行）

基线：代码 m1@5db733d8，authority AOS-001329。复习231主计划§6八步、b69方案与verification、D-waves b70。单写者仅旧thread，正式移交后由新thread接续。

## 本次新证据

- `services/aos-api/aos_api/aip_production_contract_store.py:3421` 原 revoke_evidence_bundle 使用默认 connect：普通读取 EvidenceBundleRevision、hash核验、查/追加 revoke event、Receipt、commit；该方法及_replay/_receipt未持共同advisory或源行锁。
- `services/aos-api/tests/extension_runtime/plan_restricted_evaluate_case.py:122` 受限命令要求SERIALIZABLE，锁Installation后取Registry(228,1)，对Registry可变版本FOR SHARE，再用普通SELECT读取License修订/撤销事件。b69的负例只在已提交撤销后新开事务。
- SERIALIZABLE事务在GUC/初次查询时已有快照；仅增加对不可变Evidence修订的共享锁或advisory等待，不能直接证明等待后可见新撤销。Registry已有可变status行与License append-only事件不同，不能复制Registry绿色结论。

## 下一施工精确包

1. `services/aos-api/tests/extension_runtime/plan_restricted_evaluate_case.py`：增加opt-in License并发辅助路径，使用真实 AipProductionContractStore.revoke_evidence_bundle，两个连接与pg_locks精确PID观测，有限statement/lock超时、finally清理；不直接INSERT事件替代正式writer，不改默认路径。
2. `services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py`：独立b70开关，仅signed Growth1.13 disposable aos_test_*_ti4_test，强制License和paired Receipt。编辑前补读完整相关夹具、模型与原writer调用合同。
3. 撤销先提交：受限事务先形成快照，阻塞Installation锁；真实writer完成撤销Receipt并提交后释放锁，evaluator必须42501/40001且新key Receipt0、Binding版本不增。若仍applied，保存实际RED，不把已提交负例替代此竞争窗口。
4. evaluator先提交：在可信命令持锁且Receipt外部不可见时启动真实writer；要求明确共同锁等待与提交顺序，提交后新key失败关闭，重复key/异hash/错tenant仍保持原门。没有共同锁则记录缺口。
5. 最小实现仅在RED确定根因后选现有合同能支持的方案；涉及隔离级别或新增可变权威行须先补方案和兼容论证，不通过手工GUC/缓存/owner捷径伪造授权。尤其仅锁不可变行不算快照修复。

## 验证及边界

先b70专项，再b69/默认/b67/b49/b50相邻签名PG和readiness reader回归，py_compile/diff检查；本波无页面变化，浏览器不适用，不用旧页面证据冒充首链。真库135只读，Host/worker/Provider关闭，禁商城源、旧12Run、手工run_definition、230L0与push。test-only结果不授正式实例权限。

当前只完成步骤1/8与2/8方案准备，未写测试/跑RED，未修生产代码；两项安全候选为本并发RED、W-L20实例ToolBinding来源核验。机制O4必须凭后续真实施工证据记录，不能把本方案算成已完成业务波。

## 新thread实际施工补充

2026-10-05基线f7d38b0c、docs774a2508；唯一写者新thread，旧Goalpaused、新Goalactive；迁移Task已收口。两个opt-in AOS_B70_LICENSE_REVOKE_FIRST / AOS_B70_LICENSE_EVALUATE_FIRST 独立运行，不与Registry撤销模式混合；强制b69 License和b67配对。仅b70 fixture把brief_ref/marking设为合法test-only模型格式，以便调用原writer回读；不改默认b69 fixture。writer使用原Store/默认tenant connect封装有限statement/lock_timeout和精确PID队列，不mock Store。撤销先：先block Installation、evaluator已取SERIALIZABLE快照并由pg_blocking_pids确认等待blocker，再writer实际commit/Receipt回读，释放blocker，要求拒绝+版本/Receipt不增。评测先：评测结果未提交时启动writer，精确PID观测锁等待或提前完成，以有界实际阶段裁决；必须finally释放连接/超时，无盲sleep推断。生产锁/隔离级别不改，本波先形成两个真实RED证据；之后补合同选择最小修复，不能以负门失败停整个Goal。测试资源仅现有test-only context aos-a0v-test-pg/5433 +签名OCI colima-aos-extension，conftest独立建drop aos_test_*_ti4_test，不连接18435当前真库。

## 两顺序RED后的收口范围

撤销先实测applied/Receipt1/version3；评测先writer提前commit、无共同锁等待。问题涉及SERIALIZABLE早快照+append-only撤销源，现有Evidence修订无可变head；仅锁不可变修订不充分。b70保持两显式诊断模式原失败，不设xfail掩盖，不直接改生产writer/隔离级别。专项RED是交付反证而非功能GREEN；默认/b69/b67/b49/b50相邻保持兼容。下一b71先对账各Evidence写者/消费合同，比较事务前来源栅栏与可变撤销epoch方案，冻结全锁序与回滚再隔离演练；新增权威行/隔离变更须正式设计门，不扩当前库授权。
