# W5CB4 BG00cp｜签发请求与未知结果只读对账合同文件级方案

## 上位依据与当前缺口

复习 231-4 最小权限/租户隔离、231-5 批准事件幂等与未知结果先对账、BG00ci–co。当前 API 网络 decision 默认已禁入，克隆可真实 issuer TCP 事务，但没有跨进程请求合同。不同进程不能相信 API 传来的 `actorId`/roles/“已验证”布尔值；签发端必须重新验证原始外部 OIDC JWT、tenant claim、当前 `meta_membership`、maker/checker 和 Proposal/hash。超时后的独立查询不能偷偷重发 INSERT。

## 文件级顺序

1. `services/aos-api/tests/aip/test_aip_network_issuer_contracts.py` 先 RED：请求只接受 schemaVersion=1、原始 bearer secret、精确 org/project/proposal/idempotency 与现有 `DecideActionProposalRequest`；未知字段、开发 token、空白/超长身份、错误 hash、错租户和伪 actor/roles 字段拒绝。日志/`repr`/默认 JSON 不可露 bearer。单独 Inquiry 只有相同 tenant/proposal/idempotency/requestHash 与 bearer，不能带 decision 或新审批命令；`requestHash` 必须精确等于现有 `AipActionStore.decide` 的 body canonical hash。
2. 新增 `services/aos-api/aos_api/aip_network_issuer_contracts.py`，复用 `AipContractModel` 与 `DecideActionProposalRequest`，使用 `SecretStr` 承载 JWT。合同只解析、计算 canonical request hash；不在 API 端把 token 解码后自称正式 checker，不包含 DB 凭据、SQL 或 callback。进程接线另波实现 `resolve_principal` 的独立复验和只读 Event 查询。
3. 专项与网络 producer 邻接回归、方案/代码复审、verification、m1 精确提交、上下文同步。当前无正式 IdP/不同 OS 用户时不启动进程、不向当前库写入，也不把 DTO 测试当业务批准。

## 边界

无当前库 DML/DDL、商城源读取、dev-org 写、旧 Run 重放、手工 run_definition、Host/worker/Provider、push。未知结果只能返回 unresolved 或 read-only exact Event/Receipt，绝不因“未看到”自动重发。
