# BG00EO HTTPS签名身份到消费者验证

基线AOS-001003/m1@302e4bb3。本波补既有代码的真实协议集成证据，仅新增测试，未人为制造产品RED或修改生产逻辑。

- 真实TLS HTTPS JWKS/临时RSA签名→PyJWKClient→JWT验签→resolve_principal→consumer actor门→独立caller TCP PG事务→持久attempt→独立readonly Receipt；不替换认证、消费、DB、TLS校验函数。
- 仅测试域名DNS在进程内映射loopback；SSL_CERT_FILE信任私有临时证书；不改系统DNS/信任库/.env。私钥0600/目录0700，结束删除TLS私钥，JWT签名密钥仅内存。
- 首轮句柄42424：8 passed /10.93s/exit0。增加未信任CA拒绝后累计句柄77129：**60 passed /20.61s/exit0**。

```sh
services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_network_consumer_signed_https_pg.py services/aos-api/tests/aip/test_network_consumer_service_pg.py services/aos-api/tests/aip/test_network_consumer_actor_pg.py services/aos-api/tests/aip/test_network_consumer_auth.py services/aos-api/tests/aip/test_network_consumer_attempt.py services/aos-api/tests/test_oidc_required_claims.py services/aos-api/tests/test_oidc_external_only.py --tb=short --show-capture=no
```

正向原maker签名消费后唯一head/revision/Receipt各1，刷新token仅读观察同Receipt。过期/无exp/错签名/aud/租户/actor均attempt0、业务行0；撤销maker membership后有效签名也不可读历史Receipt；移除临时CA信任后TLS握手失败，JWKS HTTP handler请求0、attempt0、PG行0。由此补齐BG00EM身份替身组合到真实签名协议的证据缺口。

仍非正式客户IdP、正式账号、跨OS进程隔离或自然首链验收；测试authority仅存在独立临时PG中。BG00EN旧org-b登录403基线债不在本次60项范围内，未声称消失。

当前库只读命令`docker --context colima-aos-extension exec aos-a0v-recovery-pg psql -X -v ON_ERROR_STOP=1 -U aos_app -d aos_current_preview_20260927 -Atc 'BEGIN READ ONLY; SELECT current_database(),version_num FROM alembic_version; COMMIT;'` → aos_current_preview_20260927|a0v_118，exit0。代码122未部署，Host/worker/Provider未启，无商城源/旧Run访问。git diff --check exit0。

下一波BG00EP：复习独立issuer启动/入口方案，给消费者冻结私有进程配置、输入与结果协议、禁凭据回落和启动前置；正式身份缺口只阻断当前实例。先计划/RED后最小入口，继续验证未知结果不重发；部署仍独立备份/克隆/零窗口。m1单写、不push，230 L0挂起。
