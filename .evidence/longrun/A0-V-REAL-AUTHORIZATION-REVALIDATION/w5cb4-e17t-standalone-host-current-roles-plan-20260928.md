# W5CB4 E17-t｜独立 Host CLI 正式角色合同文件级方案

## 上位方案与缺口

E17 正式三身份要求当前 Web/Runtime/Directory 独立、非特权、同当前签名安装库，精确 Host assignment/Owner。E17-l 已用真实 DB session user/role OID、权限和 assignment 做只读交叉校验，E17-s 固定凭据文件代次。独立 `scripts/a0v_ecommerce_runtime_host.py:_load_credentials` 仍硬编码 2026-09-12 旧角色名；若未来合法当前身份改名，该 CLI 会错误阻断，且旧名字可能给人错误引导。当前 `main` 在 Owner 权威未明时仍无条件 `FORMAL_OWNER_AUTHORITY_UNPROVEN`，不得解除。

## 最小变更与验证

1. `services/aos-api/tests/extension_runtime/test_a0v_ecommerce_runtime_host.py` 先 RED：三个任意当前角色名，只要各自 DSN 的 user/password 与受保护文件内 role/password 一致且互异，CLI 本地形状核验可过；user/password 漂移、重复 role、重复 DSN、权限错误拒绝。此测试只验证文件合同，不能代替 E17-l 真实 DB 身份。
2. `scripts/a0v_ecommerce_runtime_host.py` 仅将旧 `EXPECTED_ROLES` 改成固定 plane 集，并用 `psycopg.conninfo.conninfo_to_dict` 校对 DSN 的 user/password 与各 entry 声明，要求三 role/DSN 互异；不将值写环境或日志。签名、当前库、E17-l 物理角色/assignment/配置及 Owner 硬门原样保留。`hostId` 状态值目前不可执行，后续解除 Owner 硬门前必须绑定 E17-l report 的精确 Host ID，禁止把旧常量发布为当前身份。
3. 专项及邻接回归、真实无正式凭据只读负向；不启 Host/worker、不写当前库。

## 风险与下波

文件局部语法正确不代表合法正式身份，必须由 E17-l 的实际数据库角色/权限与 assignment 证明。修正旧 role 常量后仍不能启 Host；下一波需核 Owner/批准权威与 Host status `hostId` 绑定，并继续八配置/首链。旧 12 Run、商城源、dev-org、230 L0 保持禁入。
