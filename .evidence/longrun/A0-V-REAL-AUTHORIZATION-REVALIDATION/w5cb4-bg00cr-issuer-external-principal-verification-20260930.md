# W5CB4 BG00cr｜独立签发者外部身份门验证

- 基线：m1 `de751ad8`；任务 Receipt `W5CB4-BG00CR-20260930`；方案 `w5cb4-bg00cr-issuer-external-principal-plan-20260930.md`。
- RED：`AOS_TEST_USE_SHARED_DATABASE=1 services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_aip_network_issuer_auth.py` 退出 1，12 failed，均为缺 `aip_network_issuer_auth` 模块。
- GREEN/邻接：同环境执行 issuer auth、合同、只读对账、外部 OIDC、network producer 五个测试文件，退出 0，`38 passed, 3 skipped`；跳过项目为需具备独立 PG 实例的验证，本次未当通过。`python -m compileall -q` 与 `git diff --check` 退出 0。
- 代码复审：只新增 `aip_network_issuer_auth.py` 与测试；在读取 token 前要求显式关闭开发认证并开启 external-only，显式 HTTPS issuer/JWKS 与 audience，拒绝 loopback；现有 `resolve_principal` 验签后核对 exact tenant、非空非 `unknown` 主体。请求既不携带可信角色，也不建立路由/连接；checker 当前成员及 maker 分离仍在 `NetworkPolicyApprovalGuard.check` 的数据库事务中，不复制第二套角色逻辑。
- 当前实例：`.env` 无这些正式外部 OIDC 配置名；本波未切换 API/DB 角色、未写当前库、未创建 Approval Event/Run。正式 JWT 正向与独立 issuer 进程尚无当前 authority，测试替身仅核验组合逻辑，不充当正式身份验收。
- 方案一致性/风险：文件范围和禁入合同一致。当前风险是独立 OS 身份/IPC、真实 IdP/JWKS、当前 checker 双人及现网 HBA 未闭合；下一波在隔离克隆构造进程入口与私有接口，正式实例仍禁入。
