# W5CB4 E17-s2b｜最终 Skill 发布事务与原来源文件级方案

## 复习与现状

- 上位 231/231-3/231-9、56/64、553/554。原 `AipSkillPublicationService.publish_evaluated_revision` 必须 exact evaluated Skill、原 PASSED Gate、当前 PublicationEvent、published LogicRevision、当前 ModelRoute/RuntimePolicy，最后新 Skill 修订与 Receipt 同事务。
- E17-s2 的 `AipReleasePublicationService._verify_gate_evidence` 现在会对 Skill 在当前稳定租户事务核持久双签 proof。最终发布服务仍通过普通 `db.connect` 获取 read-committed 事务，因而原 reader 必然失败封闭；不能删 reader 或改为第二条只读连接。
- 原 `published_skill_runtime` 测试夹具产出的报告是历史 callback 代入，不是正式签名评测；不能把既有历史成功测试改名为正式发布。当前真实库也没有正式 issuer/身份/writer/Run Owner。

## 文件级顺序

1. `services/aos-api/tests/aip/test_aip_skill_publication_service.py` 或独立同目录测试：沿原 evaluated Skill/Logic/Route/Policy 生产者构造隔离临时 PG 来源，使用测试专用独立 Target/Judge 双签把原 Report 的每 case 绑定到当前持久 Suite、Run、双 Receipt 和 sidecar。先 RED：即使原 Gate/Event 有签名证据，最终发布因 read-committed 稳定快照门拒绝。错签/撤销/缺侧证/错 Event 或 Logic/Route/Policy 时新 Skill/Receipt=0。签名仅 test-only，不能记真实业务完成。
2. `services/aos-api/aos_api/aip_skill_publication_service.py`：只把最终发布动作的默认连接切到原 `connect_serializable(scope)`；调用方注入连接仍由现有签名 reader 验隔离级别。保持原锁、幂等 Receipt、exact evaluated/Logic/Route/Policy 校验、发布 payload/hash/版本与异常映射。其他服务不改。
3. 原 SkillPublicationService/ReleaseGate 及相邻 tests 通过；适用时浏览器仍展示当前实例真实 blocker。代码/方案复审明确 Gate/PublicationEvent/SkillRevision 三者分层，不把隔离签名测试视为当前正式授权。

RED 时发现 E17-s1 装配的 `except ValueError` 也包住 `EvalExecutionRejected`（其父类为 ValueError），使稳定快照缺失被泛化为“proof assembly failed”。本波先在 `aip_eval_report_proof_reader.py` 原装配处透传既有禁入异常，再让测试精确区分 read-committed 禁入与缺侧证禁入；这只修诊断，不放宽准入或改结果。

## 边界

当前 `aos_current_preview_20260927@a0v_135` 只读；Host/worker/Provider关闭；只在 `aos_test_*_ti4_test` 写 test-only 证据，dev-org 不写。不读商城源、不重放旧 Run、不手工 run_definition、不碰 230 L0、不 push。正式 EvalRun Owner/issuer/双身份/writer 与六 Binding 仍为下一阶段来源工作。
