# W5CB4 E17-s2｜原 ReleaseGate 消费签名 Skill Eval 文件级方案

## 复习与界线

- 上位 231/231-3/231-9、56 Skill 发布产品方案、64 W-F2/F3、553。原 `AipReleasePublicationService` 的 derive 与 publish 都只凭报告/Run/Suite 再硬拒 Skill；普通 LogicGraph 保持原功能。`AipEvalRunner` callback 路径不能产生正式 Skill 签名 proof，保持硬拒。
- E17-s1 已在原 `aip_eval_report_proof_reader.py` 提供同事务持久 Suite→双 Receipt/证书→当前撤销/Run/Report 的只读验证。当前生产数据库没有正式签名来源；隔离 test-only 证明机制不等于当前授权。

## 最小文件与 RED

1. `services/aos-api/tests/aip/test_aip_release_publication_signed_skill_pg.py`：标准临时 PG 中用签名 test-only fixture 走原 persisted Suite/Run/Report/sidecar，首次要求 derive 得到 PASS，预期旧硬门 RED。再检查 Gate 精确 report/hash 与当前撤销；publish 前重验同一证明。错/缺 proof、撤销、租户、Suite/hash 均不得新增 Gate/PublicationEvent。所有数据仅进 `aos_test_*_ti4_test`。
2. `services/aos-api/aos_api/aip_release_publication_service.py`：仅 derive/publish 的默认连接用原 `connect_serializable(scope)`，确保读取当前撤销与 Gate/PublicationEvent 写入在**同一** serializable 租户事务；注入测试连接亦须主动校验稳定隔离和 `aos_runtime`。Skill 分支调用 E17-s1 持久读证，抛错映射 `AipReleaseGateRejected`；不修改普通 Eval Runner、不另建快捷 Gate、不从请求接收自报签名或输入哈希。
3. 旧 `LogicGraph` derive/publish/revoke、SkillPublication 接口及相邻回归必须不退化；replay 仅返回同一已验 exact Gate/Event，不重发。浏览器只有原禁入页面，当前实例不做正式发布动作。

## 完成与风险

隔离签名 fixture 正向只算代码机制，不算正式当前 Skill 发布；正式 EvalRun Owner、issuer/身份、受限 writer ACL/凭据和六 Binding 仍独立缺失。当前真实库只读，Host/worker/Provider 关闭，不读商城源、不重放旧 Run、不手工 run_definition、不碰 230 L0、不 push。若同事务证明不能维持，就保持 Skill gate 禁入并先修这个点，不拆成两个读写事务。

复审新增依赖：原 `AipSkillPublicationService.publish_evaluated_revision` 在默认 read-committed 连接内调用 `AipReleasePublicationService._verify_gate_evidence`。本波的签名 reader 会正确拒绝这种非稳定快照，所以即使隔离 Gate 可签名通过，最终 `SkillTemplate` 发布仍不能宣称正向。后续独立小波须让该原发布事务也在 serializable 隔离级别重验签名证据，同时维持原 Logic/ModelRoute/RuntimePolicy/Receipt 与同键语义。
