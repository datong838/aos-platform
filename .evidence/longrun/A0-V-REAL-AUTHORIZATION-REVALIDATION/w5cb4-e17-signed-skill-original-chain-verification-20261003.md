# W5CB4 E17-s2c｜原 evaluated Skill 到签名发布的隔离验证

## 实施、来源与结果

- 上位 231、56/64、555 和本波文件级方案先读。原服务在 E17-s2b 后已具备稳定事务；本波新增联测首先直接 GREEN，**没有出现新的生产代码 RED，也没有修改生产代码**。不制造失败或放宽门禁来满足形式上的 RED。
- 经原 `AipSkillRegistry.publish_skill` 生成 evaluated Skill；隔离 test-only 签发材料与持久 Suite/Run/Report/双 Receipt/sidecar 用当前原读证路径验证；原 `AipReleasePublicationService.derive_gate/publish` 得 PASSED Gate/Event；原 `AipSkillPublicationService.publish_evaluated_revision` 得 published Skill 与 Receipt。parent/Gate/Event/Route/Policy/Logic 精确引用、同键重放不双写均断言。
- 错 PublicationEvent 被拒；签发 Target 身份撤销后用新幂等键再次发布被拒，新发布 Receipt 总数保持1。签发键和原始 Run 只存在自动创建并销毁的 `aos_test_*_ti4_test`；cleanup 在确认临时库名后按 org-org/dev-project 精确删除本测试签名行。当前权威库没有测试写入。

| 命令/检查 | 结果 |
|---|---|
| 单项 `pytest -q tests/aip/test_aip_skill_publication_service.py::test_original_evaluated_skill_signed_gate_event_publishes_once -x` | 1 passed，exit0；包含正向、错事件、撤销与幂等断言。 |
| 相邻 `pytest -q tests/aip/test_aip_skill_publication_service.py tests/aip/test_aip_release_publication_service.py tests/aip/test_aip_release_publication_signed_skill_pg.py tests/aip/test_aip_eval_report_persisted_assembly_pg.py` | 24 passed、1 原有 xfail、7 warnings，exit0。执行时 `AOS_DATABASE_URL` 指向当前服务地址，conftest 实际创建/销毁独立 `aos_test_*_ti4_test`，本测试不写当前库。 |
| `python3 -m py_compile` 与目标 `git diff --check` | 均 exit0。 |
| 重启后现场只读 | API `/v1/health` 200，Web `/aip/skill-publish` 200；`colima-aos-extension` 中 PG 使用 `aos-a0v-recovery-pg-data`，只读 SQL 回读 `aos_current_preview_20260927@a0v_135`，18181 无监听。浏览器 org-org/dev-project 页面37条仅已评测、已发布0、三项 blocker、按钮 disabled、无工作台入口；截图/AX在本轮 CUA 结果。 |

## 方案复审与边界

- 联测证明签名消费代码在隔离数据库可连通。Logic/Route/Policy 本轮沿既有测试授权夹具，Suite/Run/Report/签发材料为 test-only 种子；因此**不证明这三项原生产者、正式 Run Owner/issuer/writer，或当前真实实例已发布**。正式实例仍为已发布0、active Binding0、frozen Plan/八配置/Host Owner/首链 pending。
- 当前真实库只读、Host/worker/Provider关闭。下一波 E17-s3 应查正式 EvalRun Owner/issuer/Target/Judge/writer 的合法来源与受限启动；若当前实例缺身份，只阻断该实例，继续原 Logic/Route/Policy 生产者及 Binding 的独立代码项。未重放旧 Run、未手工 run_definition、未读商城源、未写 dev-org、未 push。
