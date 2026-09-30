# BG00EN 外部OIDC必需声明验证

基线AOS-001002/m1@4c2be329。配置只读检查：仓库.env外部issuer/JWKS/audience未配置，当前执行器环境同样未配置，services/aos-api/.env不存在；不推断所有其他供给不存在，未读取/输出凭据。正式consumer没有HTTP/IPC入口。

真实RSA+本地HTTP JWKS→PyJWKClient→jwt.decode→resolve_principal，未替换验证函数：RED句柄99559，2 failed（缺exp/sub被接受）/8 passed/10.27s/exit1。只修改oidc.py外部JWT decode一行，external_only时required exp/sub/iss/aud，非external-only路径保持原行为。

专项及相邻命令：
```sh
services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/test_oidc_required_claims.py services/aos-api/tests/test_oidc_external_only.py services/aos-api/tests/test_external_jwks.py services/aos-api/tests/test_jwks_failover.py services/aos-api/tests/aip/test_network_consumer_auth.py services/aos-api/tests/aip/test_aip_network_issuer_auth.py --tb=short --show-capture=no
```
句柄41159：46 passed / 16.80s / exit0。覆盖正常正租户、必需声明、过期、错issuer/audience/tenant、错签名、开发fallback拒绝及原认证适配。

完整相邻范围另含test_oidc_auth.py，句柄47930：50 passed / 1 failed /30.49s/exit1。失败test_jwt_login_non_dev_token为既有org-b/prj-b登录返回403而测试期望200。用独立Python进程将`git show HEAD:services/aos-api/aos_api/oidc.py`编译回已导入oidc模块再运行同一测试，未改工作树；句柄57128同样1 failed /6.82s/exit1，证明不是本次改动引入。该失败保留登记，不能声称全部相邻全绿。

复审：签名/期限/issuer/audience仍交由原JWT库验证，未复制认证算法、改变全局默认值或放宽HTTPS配置门。临时私钥仅在测试内存，不写日志/文件；HTTP仅隔离测试JWKS载体，不代表正式HTTPS/OIDC或当前身份验收。无DB迁移、无真实库写、无Host/worker/Provider，不读商城源/旧Run，230 L0挂起。git diff --check exit0。

下一波BG00EO：沿BG00EM私有消费者继续检查正式HTTPS/JWKS身份供给及隔离入口配置；实现真实签名验证到消费的隔离集成，仍禁止伪造正式账号。旧登录403用独立租户目录fixture波处理，不为让测试通过而绕过目录门。当前部署/首链继续pending。
