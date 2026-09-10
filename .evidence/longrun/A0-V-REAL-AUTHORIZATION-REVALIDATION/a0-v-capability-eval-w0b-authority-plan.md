# A0-V Capability EvalPack 与 W0B Authority 实施方案

## 1. 目标与依据

目标是在 `aos_meta_head` 中为 10 个 canonical ecommerce Capability 建立与当前已签名 v4 制品同源的 EvalPack，并验证 21 号 W0B ADR 的八类公共生产对象已由正式 PostgreSQL authority 承载。完成后发布每个 Capability 的下一条 immutable revision，只移除 `eval_pack_unavailable` 与 `w0b_contracts_unavailable`。

依据：

- `21-AIP-W0B八公共生产对象Authority-ADR与W2实施清单.md`；
- 当前签名制品树 `sha256:26a5942e8087252df8f72e5430e4c4c6e42c906a8f814fe2df428d33c1293950`；
- Canonical 安装 `c1eb714f-56de-4f28-ba06-c3440b3d18cb` 的 approved generation；
- `AipEvalPackRegistry`、`AipCapabilityRegistry` 与现有 W0B migrations/Store 是唯一写入路径。

## 2. 施工文件

- 新增 `services/aos-api/aos_api/aip_capability_w0b_authority.py`：纯结构判定和 readiness reason 收敛；不连接数据库。
- 新增 `scripts/a0v_capability_eval_w0b_authority.py`：固定租户、固定制品、正式 Registry 写入和 exact readback。
- 新增 `services/aos-api/tests/extension_runtime/test_a0v_capability_eval_w0b_authority.py`。
- 证据写入 `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/`。

## 3. W0B 八对象结构门

审计下列对象族：TaskBriefRevision、EvidenceBundleRevision、EvalContractRevision、ResponsibilityPlanRevision、StageTemplate、ArtifactRelation、ReviewIssue/ReturnDecision、ImpactPreview。对应 15 个当前 canonical relations 必须全部存在；每个 relation 必须同时满足：

- 含 `org_id/project_id` tenant key；
- RLS=true、FORCE RLS=true；
- 至少一个 PostgreSQL policy；
- 生产合同 Store 中存在相应 create/get/freeze 或 append 路径；不以 Router/UI/YAML 代替 owner。

结构门只证明 W0B authority 已实现，不证明某租户已经创建 Task、Brief、Evidence、Plan 或 Run。

## 4. EvalPack 同源门

- build receipt、qualification receipt 与 v4 输出树必须继续通过首装脚本的 source/tree/hash 校验。
- 每个 Capability 的 EvalDataset/Suite 使用固定 ID/revision=1。
- dataset source hash 取签名 v4 `content/agents/ecommerce-capability-catalog.json` 的真实文件 SHA-256；输入 ArtifactRef 绑定该文件。
- expected ArtifactRef 绑定签名 v4 `evidence/bundle-evals.json` 的真实文件 SHA-256；不生成占位 hash。
- suite target 固定到该 Capability 当前 r1 content hash；redaction policy/judge 使用固定合同 ID，但其 hash 从同一签名 evidence 文件与 ID 的 canonical 组合计算。
- Registry 首次写入后必须 exact readback；既有同 ID/revision 漂移则停止。

## 5. Capability revision 与重放

- 当前基线必须恰为 10 个 r1 published Capability，且 blockers 精确包含 `eval_pack_unavailable` 和 `w0b_contracts_unavailable`；部分 r2 或不同 parent/hash 视为漂移。
- 新 r2 exact parent=r1，保留所有 schema、alias、risk、policy 与 source refs，挂载 EvalPack；只移除上述两个 blocker。
- `provider_unknown`、`aip7_route_authority_unavailable` 必须保留，readiness 继续 `blocked`。
- 首次可新增 10 Dataset、10 Suite、10 Capability revision；重放读取相同对象，mutation=0。
- 不创建 CapabilityBinding/SkillBinding，不激活 Agent，不创建 ResponsibilityPlan。

## 6. 安全、备份与退出

- apply 只接受 `colima-aos-extension/aos-a0v-recovery-pg/aos_meta_head`。
- 写入前独立 `pg_dump`，保存路径/hash/size；失败保留前置不可变对象并由同 ID 续跑。
- canary 的 EvalDataset/Suite 及全部 runtime authority 必须为 0。
- Provider invocation、external publication、业务 mutation 为 0。
- 首次与重放通过、10/10 r2 exact readback 后退出 `A0V_CAPABILITY_EVAL_W0B_AUTHORITY_GREEN`；这不是 Provider、Binding、Agent 或 A0-V 总门 GREEN。
