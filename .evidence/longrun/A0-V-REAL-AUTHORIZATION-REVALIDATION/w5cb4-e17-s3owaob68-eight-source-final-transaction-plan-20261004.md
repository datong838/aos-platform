# b68 文件级方案：八类依赖可信来源与最终事务

## 上位依据和当前代码

- BIND-1 的八类组织运行依赖是 Provider、Route、Policy、Eval、License、Data、Tool、Budget；231-3 要求当前 signed Installation/RuntimeBinding/epoch 与运行授权共同准入。b67 已在 signed Growth1.13 disposable PG 中证明 blocked evaluator 的安装/Registry 锁与 Binding↔Receipt 配对，但未计算 available。
- `AipBindingReadinessService.for_transaction(conn)` 能把已有 Reader 绑定到同一连接；b45 仅证明未提交 CapabilityRevision 的可见性，不能证明调用方具有正式读权限、签名/健康来源或可写权限。当前 `AipCapabilityBindingService.evaluate()` 使用独立 Reader 在写事务前预计算，普通 issuer 已被 b65 禁入。

## 权威来源矩阵（按当前实现，非当前实例正向）

| 类别 | 代码读取的权威 | 已有校验 | 本波发现的缺口 |
|---|---|---|---|
| Provider | `AipModelRuntimeResolver` → ProviderInstanceRevision、健康、Route 候选 | exact provider ref/健康新鲜度与 route.selectedProvider 一致 | 当前正式 Provider 身份和健康来源未齐；不可拿目录定义替代实例 |
| Route | `AipModelRuntimeStore.get_route`、当前 head、候选模型 | exact revision/hash、active、ready | final transaction 内必须锁当前 head，防独立 Reader 漂移 |
| Policy | `get_policy` 与 route.runtime_policy_ref | exact hash、active、kill switch | 需与 Route 同事务并核预算指针 |
| Eval | `aip_release_gate_decision`、`aip_eval_contract_revision` | passed/hash/时间窗、contract frozen/hash | 两种 ref 都需当前租户权限及撤销/过期处理 |
| License | `aip_evidence_bundle_revision` + revoke event | frozen、license summary、未撤销 | `ResourceRef` 不含内容 hash，需由可信查询固定精确版本/撤销状态 |
| Data | `aip_eval_dataset_revision` 或 EvidenceBundleRevision | exact hash；EvidenceBundle frozen/未撤销 | 未覆盖所有 O1/管道数据种类；未知 kind 应继续 blocked |
| Tool | W-D3 明确将定义级 `requiredToolRefs` 投影为 frozen `EvidenceBundleRevision`，`exact_assets_available` 可按 exact hash/revoke 校验 | 定义级 exact ref 有真源 | W-L20 `aip_tool_binding` 是实例执行分配；该层是否满足运行门仍需独立核验，不能以 W-D3 定义级 ✓ 冒充实例可调用 |
| Budget | `aip_model_governance_policy_head/revision` 与 runtime policy ref | current revision/hash/active/有效期 | final transaction 内需和 Route/Policy 同步，并核审批/预算义务 |

## 本波文件与判据

1. **b69 复审纠正**：初版把 `aip_tool_binding` 当成定义级 ToolRevision，误判 Tool 无 exact 真源。上位 W-D3 与 `aip_capability_tool_deps.py` 证明定义级 Tool ref 用 frozen `EvidenceBundleRevision`，已有 exact hash/revoke 判据；W-L20 的实例 ToolBinding 是另一门。保留该纠错记录，不再用“Tool 真源缺失”作为 b68 结论。
2. 本波在 `services/aos-api/tests/aip/test_e17_s3owaob45_transaction_readiness_pg.py` 选已有权威的 License 读链：disposable PG 同事务写 frozen evidence、重读并撤销，独立 Reader 不可见；这是首项事务可见性证明，尚非受限正式身份或八维 available。signed b67 最终命令对缺项继续 blocked，不给当前库造配置。
3. 继续逐项把查询、权限和锁序接进受限 final transaction；八类齐全且 signed 当前安装/Registry 未漂移，才能推进 available 正向。正式身份/唯一136/当前库切换仍分别受备份、恢复和零执行窗口门控。

## 硬边界

仅 org-org/dev-project 正向，dev-org 零副作用；当前真库135只读，Host/worker/Provider关闭，不读商城源、不回放旧 Run、不手工 run_definition、不碰230 L0、不 push。test-only fixture 不能充当正式身份或真实业务验收。
