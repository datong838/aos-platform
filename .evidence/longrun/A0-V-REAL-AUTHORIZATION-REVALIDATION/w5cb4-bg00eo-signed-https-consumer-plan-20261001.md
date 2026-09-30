# BG00EO HTTPS签名身份到消费者隔离集成

基线AOS-001003/m1@302e4bb3，复习BG00EM私有服务、BG00EN必需声明及issuer外部HTTPS配置门。本波验证既有实现，不为了RED人为改产品逻辑。正式身份尚缺，当前库118只读。

唯一测试文件`services/aos-api/tests/aip/test_network_consumer_signed_https_pg.py`：临时RSA签名密钥、临时TLS CA/服务器证书、本机随机端口HTTPS JWKS；仅把测试域名DNS映射到该本机端口并在本测试环境信任临时CA。保留真实TLS证书验证、PyJWKClient、JWT验签、resolve_principal、consumer身份门、SQL函数、数据库连接与attempt文件，禁止替换认证/消费函数或关闭TLS证书验证。

配置/密钥只留临时私有测试目录与内存，绝不写正式.env或系统DNS/信任库。DNS映射仅进程内特定.test域名，其他地址仍走原解析；清理server/thread/monkeypatch。该载体不是正式外部IdP、生产账号、自然业务或进程隔离验收。

覆盖：真实签名原maker→唯一Receipt→刷新token只读回查；过期/无exp/错签名/错aud/跨租户JWT不写attempt或PG；同租户错actor通过JWT后在数据库拒绝；成员撤销后历史Receipt也不绕过原actor门。依次专项/累计验证与复审，再证据/精确m1提交/AOS+Prime/D-waves。当前真实实例不切换、不启Host/worker/Provider、不读商城源、不重放Run、不手工run_definition、不push，230 L0挂起。
