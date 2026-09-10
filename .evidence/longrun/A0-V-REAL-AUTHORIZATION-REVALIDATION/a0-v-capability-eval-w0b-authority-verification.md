# A0-V Capability EvalPack 与 W0B Authority 验证

## 结论

2026-09-10 在隔离恢复库 `aos-a0v-recovery-pg/aos_meta_head` 完成 Capability EvalPack/W0B authority 首次与重放。首次新增 10 个 DatasetRevision、10 个 EvalSuiteRevision、10 个 Capability r2，共 30 个 immutable 对象；重放 mutation=0，10 个 r2 的 ID/revision/content hash/EvalPack ref 完全一致。

阶段退出为 `A0V_CAPABILITY_EVAL_W0B_AUTHORITY_GREEN`。总依赖审计已从 `capabilityEvalAndW0b` 前进到 `providers`，下一确定动作是 `ESTABLISH_REAL_PROVIDER_INSTANCE_AUTHORITY`。

## W0B 与同源证据

- 15/15 W0B canonical relations 均包含 `org_id/project_id`，RLS=true、FORCE RLS=true、policy count>=1。
- 22/22 `AipProductionContractStore` 对应方法可达。
- 签名 v4 树：`sha256:26a5942e8087252df8f72e5430e4c4c6e42c906a8f814fe2df428d33c1293950`。
- Capability catalog 文件 SHA-256：`0d33aac853f9f7cac835ea97cd8409388a9c4afe22ddec3b4a8eb668c72acf5a`。
- bundle eval evidence 文件 SHA-256：`02b181ca7d55990bbca1e2e923a24eddefe97cc34f596c82def301d22563c4f6`。
- runtime policy 文件 SHA-256：`2ff91b4c0b34906fcc18b40a467cb786835d6168a6301f8abc9647476417cd4f`。

10 个最新 Capability revision 均已移除且只移除 `eval_pack_unavailable`、`w0b_contracts_unavailable`；`provider_unknown` 与 `aip7_route_authority_unavailable` 继续保留，readiness 仍为 blocked。

## 备份、测试与效果

- pre-mutation backup：`sha256:987d7777ded964fa70a55923a13e8fcba195b8371ab6fc4d001110aef9092eaf`，4,353,132 bytes。
- 专项及邻接合同：12 passed；修正 latest-revision 审计后复跑 9 passed。
- preflight SHA-256：`a7060c1e6f192d4f54095428a5ca389856c90b76cbda854900d7c2afa4747b4e`。
- first apply SHA-256：`cf8601b3a30f3586b1535d98ed987e9c69f63b22be9c448873b9759cc3905430`。
- replay SHA-256：`b95f125e5005168cbfdd8c56163c16744a46ef69fcbe3eec1dc2639bad0abb52`。
- post-audit SHA-256：`1a6297820c46efeba2235806aca5d90150e56c3b223f7d75973b13ce873cb206`。
- canary Dataset/Suite/CapabilityBinding 全部为 0；Provider invocation=0，external publication=0。

## 边界与下一门

本阶段没有创建 CapabilityBinding、SkillBinding、Agent activation 或 ResponsibilityPlan，也没有调用 Provider。下一阶段必须建立真实 ProviderInstance authority，并验证当前健康；Prime/Copilot OAuth 不属于 AOS Provider 凭据，不能消费或转换为 AOS runtime secret。
