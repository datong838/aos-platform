# 显式有限JWKS时钟容差实际验收

先r1默认5433不可达setup16error，没有业务RED，未计通过；正确18431/aos_app标准独立UUID库r2实际8FAIL/8PASS，明确新显式容差与非法配置缺口。最小生产增量10行：默认0、只接受ASCII整数0..5，仅原JWKS decode的leeway；algorithms/issuer/audience/required claims/tenant/默认Dev不动。

第一累计34PASS/1FAIL：原test_jwt_login_non_dev_token的bob/org-b/prj-b未注册目录而预期200。独立exec当前HEAD未改oidc.py同例仍403/AUTH_TENANT_UNKNOWN，证明既有fixture缺陷而非回归。独立fixture Task先反证未登记403，再只独立aos_test_*_ti4_test库明确注册test目录后验证同JWT成功；不改production注册门、mock/skip/xfail。

最终35PASS0skip0fail，覆盖真实RSA/JWKS显式2下iat+1与小expiry合法、默认严格、iat/nbf/exp越界拒绝、非法配置、签名/issuer/aud/required/crossScope与原OIDC相邻。当前真实Keycloak用户datong838密码grant→原resolve_principal：实际签名/sub/固定双租户/admin/markings全过，跨org/project及dev拒绝，单一selftest refresh session原logout204；本人互动登录未观察。此为独立进程原验证器，live API75128旧冻结代码/配置未变，不能说当前Web已能用本机账号登录、8台已恢复或正式Goal通过。

风险：显式leeway同样对exp/nbf容差2秒，是配置明示的认证时间边界，默认0，max5；不得套到Budget/健康/Source原授权时间。无需系统改钟或sleep绕验证。方案/代码一致，生产只oidc.py10行，原22用户改动保留。当前冻结API需新正式候选与接线后独立验收，不假称热加载。
