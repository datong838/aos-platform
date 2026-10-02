# W5CB4 E17-s1｜Skill 正式发布来源与签名 Eval 读证方案

## 上位方案与当前事实

- 231-3 的 BI 配置只接受当前 frozen Plan；56 技能发布产品方案和 64 W-F2/F3 要求 exact evaluated Skill、Eval 放行、发布事件、Receipt/幂等，随后才创建 active SkillBinding。552 的签名安装链因六个绑定缺失在原 readiness 门拒绝，不能手插绑定。
- `AipSkillRegistry.create_binding` 要求 exact published Skill 和本租户发布来源，`update_binding(active)` 再核当前可用 readiness 与未漂移的依赖快照。`AipSkillPublicationService.publish_evaluated_revision` 要求原 ReleaseGateDecision 和 PublicationEvent。
- `AipEvalRunner.run` / `run_by_contract` 对 SkillTemplate 直接失败关闭；普通 callback 执行及多事务 Run/Report 不能作为正式签名来源。`persist_signed_skill_eval_report` 可在独立 writer 的单事务写双签 Receipt/Report/sidecar，但要求事先已成功的精确 EvalRun，当前实例仍缺正式 issuer/identity/writer/Run Owner。
- `AipReleasePublicationService.derive_gate` 与 `_verify_gate_evidence` 当前均无条件拒绝 Skill；原 `read_verified_skill_eval_report` 能在 `aos_runtime` 的稳定租户快照逐 case 验当前 root、identity、撤销、双签、Run、Report、sidecar，但由调用方提供独立的 suite input hash 和证书/Receipt。不能直接删掉发布门。

## 文件级最小施工顺序

1. `services/aos-api/aos_api/aip_eval_report_proof_reader.py`：增加**只读持久来源装配**入口，在调用方同一 repeatable-read/serializable 租户事务中从 exact Suite 取得全部 case 的 input hash；从同 Run/Report sidecar 精确取 target/judge Receipt，并依 identity 取证书。要求 case 集合相等且无多余/重复；Pydantic 解析后调用原 `read_verified_skill_eval_report` 深校验。不能从 Receipt 自报 input hash 充当独立预期，也不能自签/写库。
2. `services/aos-api/tests/aip/test_aip_eval_report_proof_reader.py`：先 RED 缺装配入口，再用隔离临时 PG 的签名 test-only fixture 验全 case 正向及缺 Suite、错 input、缺 Receipt、撤销、错租户/角色、非稳定快照负向；全部回滚。测试签名只证明机制，不计当前实例授权。
3. 下一小波才改 `services/aos-api/aos_api/aip_release_publication_service.py`：derive/publish 在同一个 serializable 事务调用上述装配，只有签名证据完整且当前时点有效才计算/消费 Skill gate。不得先放开 `AipEvalRunner`，不得通过第二连接造成撤销检查与发布写入竞态。原 LogicGraph 途径保持原结果。
4. 更后的独立波：补合法 Skill EvalRun 创建 Owner、正式 Target/Judge 签发/撤销与受限 writer ACL/凭据来源；原生产者走 evaluated→gate→publication→published→CapabilityBinding/active SkillBinding，再回 552 的 Plan freeze。当前正式身份缺失只阻断当前实例，不阻断此处隔离读证研发。

## 边界与验收

- 仅 `org-org/dev-project` 作正向；`dev-org` 只作零副作用隔离读证负例。当前 `aos_current_preview_20260927@a0v_135` 只读，Host/worker/Provider 关闭；不读商城源、不重放旧 12 Run、不手工 run_definition、不碰 230 L0、不 push。
- 本波成功判据仅为：持久读证装配在 test-only 签名隔离 PG 可核正向并严格拒绝缺/漂移；普通发布门仍保持禁入。不能据此声称 Skill 已发布、六绑定 active、Plan frozen 或自然首链完成。
