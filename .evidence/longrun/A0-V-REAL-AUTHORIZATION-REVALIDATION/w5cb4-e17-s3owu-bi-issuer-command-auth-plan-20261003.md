# s3o-w-u 第一切片｜BI 正式发行命令与身份重验

## 当前事实与上位约束

- 依据 231-3 安装与 Plan 同事务权限复核、231-9 原 AgentInstance 六身份、618 接续及 E17 D-wave。当前 HTTP BI prepare/rebind 默认 503；真实库/进程没有正式 BI issuer DB 登录、独立 OS UID、私有凭据与六 Agent 正式来源，不能当前放行。
- 可复用 `aip_private_service_transport` 的不同 UID/kernel peer 和单帧通信约束，以及 `aip_network_issuer_auth` 的外部 HTTPS OIDC 配置门与 `resolve_principal`。后者按每个请求重新验 JWT，不能信 API 传来的 actor/角色/tenant GUC。
- 本切片只冻结 BI issuer 可接收的精确命令和每请求身份重验；不实现发行进程或当前 DB migration，不把 test-only issuer/克隆说成当前正式实例。

## 文件级步骤与验收

1. `services/aos-api/tests/aip/test_aip_bi_plan_issuer_contracts.py` 与 `test_aip_bi_plan_issuer_auth.py` 先 RED：prepare/rebind 仅接 schema1、精确租户、规范 UUID、强 ETag 版本和非空幂等键；不接 actor/自报权限/多余字段；SecretStr 不泄露 bearer。外部 OIDC 配置缺失、dev token、错租户/非 OIDC/空 actor 禁入；每次命令重验一次 JWT。
2. `services/aos-api/aos_api/aip_bi_plan_issuer_contracts.py` 增最小命令 DTO，严格字段/长度，不携带 actor 或 DB 角色；`aip_bi_plan_issuer_auth.py` 复用正式 OIDC 配置门、以原认证器重验并核 claims 绑定 scope。不得在此增加 DB 写/IPC 重试。
3. 专项与现有 network issuer auth/contract、BI HTTP 相邻测试，`py_compile` 与 diff/方案复审。当前路由继续 503，真实库只读。结果写 verification；精确提交后更新 D-wave、619 续接及 Authority/Prime。

## 下一切片 / 风险

- 严格命令只是入口合同。正式私有 IPC、独立 UID/0600 凭据、独立 DB 登录、受限函数/ACL、durable attempt/只读 Receipt 对账仍待施工；不能因为 DTO 与模拟认证测试通过而开放 HTTP。
- 若外部 IdP/正式六 Agent 来源仍不存在，只阻断当前实例；隔离环境继续构建可验证的发行服务及全链迁移/恢复证明。任何未知提交结果只读对账，不重发。
