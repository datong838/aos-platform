# BG00EN 外部OIDC必需声明门

基线AOS-001002/m1@4c2be329，复习BG00EM原actor/外部认证、现有oidc.py、external-only及external-JWKS测试。当前仓库.env及执行器环境均未配置外部issuer/JWKS/audience，services/aos-api/.env不存在；这只证明已检查来源缺配置，不穷尽其他正式供给。私有consumer服务无HTTP/IPC接线。

具体缺口：`_verify_jwks`的jwt.decode验证exp存在时的值，但未要求exp存在，合法签名的无期限token可能被接受。此缺口影响正式consumer依赖的resolve_principal，优先真实RED复现。

文件：`services/aos-api/tests/test_oidc_required_claims.py`新建临时RSA密钥+本地HTTP JWKS服务，经实际PyJWKClient、jwt.decode、resolve_principal，不替换这些函数。覆盖缺exp/sub/iss/aud、过期、错签名/租户和正常正租户。仅测试HTTP载体，不降低consumer要求外部HTTPS的门；不代表正式身份供给。

最小实现：`services/aos-api/aos_api/oidc.py`仅在external_only模式为外部jwt.decode指定required claims exp/sub/iss/aud，沿用库验证签名/期限/audience/issuer，不复制JWT算法或引入fallback。非external-only行为不变，global默认鉴权技术债不在本波重写。

RED→最小更改→OIDC专项及consumer/issuer相邻回归→复审→verification→m1精确提交→AOS/Prime及D-waves。当前真库只读，无账号/Run/Provider/Host写入，不读商城源、不push，230 L0挂起。当前部署与实际OIDC/首链仍独立未完成门。
