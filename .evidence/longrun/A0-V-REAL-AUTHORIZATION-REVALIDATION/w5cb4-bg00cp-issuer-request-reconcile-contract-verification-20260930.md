# W5CB4 BG00cp｜签发请求与只读查询合同验证

## 依据和 RED

接 AOS-000945，按 231-4/231-5、BG00ci–co 先写 `w5cb4-bg00cp-issuer-request-reconcile-contract-plan-20260930.md`。独立签发服务不能信 API 自报 actor/roles；未知结果只发查询，不重发批准。新专项首次 RED：缺 `aip_network_issuer_contracts` 模块，pytest 收集退出2。

## 实现与结果

新增严格 `NetworkIssuerDecisionCommand` 与 `NetworkIssuerDecisionInquiry`。schemaVersion 固定1；只收原始 JWT 形态的 `SecretStr`、精确 tenant/proposal/idempotency 与现有 `DecideActionProposalRequest`；额外 actor/roles/decision 字段拒绝。`request_hash` 精确复用 `AipActionStore.decide` 的 body canonical hash；`inquiry()` 只生成原 tenant/proposal/key/hash 的查询合同，`matches()` 拒绝不匹配，不含新审批命令。默认 `repr`/JSON 不泄漏 bearer，签发端仍需独立验证签名/issuer/audience/tenant和成员。

专项10 passed；producer/consumer邻接20 passed、4 skipped、7 warnings，退出0；`py_compile` 和精确 diff check退出0。没有实际 IPC、签发进程、Event 只读查询或当前库写入；DTO 正例不是真实 OIDC/第二 checker 或业务批准证明。

## 剩余

下波 BG00cq 实现只读 Event/Receipt 精确对账和查询端真实 OIDC 重验，再接不同OS用户/私有socket的签发进程。当前 HBA trust、issuer NOLOGIN、API默认网络审批禁入、binding0、Host/worker/Provider关闭；首链仍待证。无商城源读取、dev-org写、旧Run回放、手工run_definition、push。
