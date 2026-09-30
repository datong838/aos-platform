# W5CB4 BG00cr｜独立签发者外部身份准入文件级方案

## 上位方案与当前缺口

复习 231 主计划、231-4 租户和低权限边界、231-5 独立 maker/checker 与未知结果先对账，以及 BG00ch/cp/cq 的外部 OIDC、严格请求和只读对账合同。当前 `aip_network_policy_action_producer.py` 已在 `decide` 事务内用 `meta_membership FOR SHARE` 重验当前 checker、与 maker 区分；普通 API 缺独立签发连接会禁入。缺口是独立签发者接收命令时尚无专用外部 OIDC/JWT 和 exact tenant 准入门，不能仅凭 DTO 的 JWT 形状与调用者自报角色签发。

## 本波范围与文件

1. 新增 `services/aos-api/tests/aip/test_aip_network_issuer_auth.py`：先 RED，覆盖缺外部配置、开发 JWT/本地 JWKS、错租户、空 subject、不可用 issuer/audience/JWKS，以及秘密不得进入异常。正向仅用受控外部验签替身证明组合接口，不视为正式 IdP 验收。
2. 新增 `services/aos-api/aos_api/aip_network_issuer_auth.py`：以 BG00cp 命令/Inquiry 为输入，先校验显式 `AOS_AUTH_ALLOW_DEV=0`、`AOS_AUTH_EXTERNAL_ONLY=1`、外部 HTTPS issuer/JWKS URL 与显式 audience，再调用既有 `resolve_principal` 验 JWT 签名、有效期、issuer/audience 与 claim tenant；要求 exact `org-org/dev-project` 对应请求值、非空 subject、`token_kind=oidc`。不接受请求带来的角色作为授权依据，不建立 HTTP 路由或数据库连接，不记录 token。
3. 复审 `NetworkPolicyApprovalGuard.check` 在签发事务中的 checker 当前成员、maker 分离、Proposal/tenant 绑定，保持该权威检查不复制为另一套易漂移逻辑。只读 Inquiry 同样重新认证；未知结果仍由 BG00cq 查询，不重发。
4. 专项和邻接回归、静态检查、verification、D-waves/上下文和 m1 精确提交。下波才处理独立进程/IPC、正式 OS 用户与 IdP 配置及克隆端到端验证。

## 禁入与回滚

当前正式库只读，现网 `aos_app` API 不切换，Host/worker/Provider 保持关闭；无正式 IdP/独立进程就不产生批准 Event。测试替身、开发 JWT 或单一 owner 不算正式 checker。回滚只移除新增门与测试，不改数据库、迁移、业务路由或当前数据。
