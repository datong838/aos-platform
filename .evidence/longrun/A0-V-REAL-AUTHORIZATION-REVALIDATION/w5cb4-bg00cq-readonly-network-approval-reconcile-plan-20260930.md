# W5CB4 BG00cq｜网络批准未知结果只读对账文件级方案

## 依据与缺口

复习 231-4 租户/非 owner/只读查询和 231-5 审批幂等、未知结果先查 Receipt 不重发，结合 BG00cj DB Event 门与 BG00cp 请求/Inquiry 合同。`aip_action_approval_event` 对同租户 idempotency_key 唯一，含 proposal_id/request_hash/decision；当前真实库 Event0，克隆 BG00cm 保留一条测试 Proposal 但 Event0。必须区分“已观察到精确 Event”“同 key 冲突”“未决”，未决不可授权再次 INSERT。

## 文件级顺序

1. `services/aos-api/tests/aip/test_aip_network_issuer_reconcile.py` 先 RED：连接必须 read-only、非 owner、`session_user=issuer/current_user=runtime` 与 transaction-local tenant 精确一致；查询只按 tenant/idempotency，联结 Proposal 限定 network action，精确比对 proposal/requestHash。无行输出 UNRESOLVED、错 proposal/hash/action 输出 CONFLICT、精确行输出 OBSERVED。克隆真实读只证明 UNRESOLVED；正向行/冲突的纯逻辑测试不是正式业务批准。
2. 新增 `services/aos-api/aos_api/aip_network_issuer_reconcile.py`，只做参数化 SELECT，不写 Event/Proposal、不执行 `decide`。返回不可变状态与最小 Event id/decision；数据库/角色/tenant 条件不满足直接拒绝。调用方不得把 UNRESOLVED 解读为可重发。
3. 独立进程入口下一波用 BG00cp Inquiry 中的原始 JWT 重新做外部 OIDC 签名、tenant claim、当前 checker 成员校验后才调用本核心。当前实例无正式 IdP/OS 隔离，不能挂 HTTP 或启 issuer。
4. 专项、邻接、隔离克隆只读负例、方案/代码复审、verification、精确提交和上下文同步。

## 止损

当前库只读、不读商城源、不写dev-org、不启Host/worker/Provider、不回放旧Run、不手工run_definition、不push。任何查询超时、连接断开或行未出现都维持 UNKNOWN/UNRESOLVED，绝不重发批准。
