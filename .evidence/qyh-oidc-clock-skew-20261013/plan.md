# 当前本机OIDC有限时钟容差

用户明确建立本机人类管理员登录并提供账号，已有人工审批不重复。实际原password grant已成功签发，Keycloak basic scope/sub已修复，但原AOS JWKS验证因iat未来拒绝。实际host/VM midpoint measurement VM领先1.365秒，timesync service ACTIVE但offset1.495s；不能伪造JWT时间、关闭iat/expiry/signature或加sleep让一个自测变绿。

文件仅services/aos-api/aos_api/oidc.py与tests/test_oidc_clock_skew.py。新增公开配置AOS_OIDC_LEEWAY_SECONDS：默认0，严格整数0..5（无效显式值拒绝），仅原JWKS验证jwt.decode传leeway；原algorithms/issuer/audience/required exp-sub-iss-aud和tenant绑定不改。当前本机接线显式2秒，不修改系统时钟、Source授权/健康/Budget时间或默认开发行为。不是所有Auth自动放宽，不假称liveAPI已接入。

先真实RSA/JWKS RED：显式2下iat+1应通过、+3应拒绝；默认0拒绝future；exp-1在2秒内可接受、exp-3拒绝；错误签名/aud/issuer/缺sub/跨租户及非法配置均拒绝。冻结测试时钟防边界波动，实际网络/真实签名验证保留。最小实现后原OIDC required-claims/external-only/auth全部相邻，最后真实本机Keycloak用户credential+原验证器/双租户/dev拒绝与单次session logout自测新r4，token/password不记录。原33个?不报虚假计数，以实际输出为准。

回滚撤配置与该两文件增量；默认0保持原行为。所有现有22用户改动保护，正式Source/八配置/资源/8台与完整经营Goal仍未完成。用户指定账户及本机身份Task仍ACTIVE，源码修复不自动加载服务或授执行权限。
