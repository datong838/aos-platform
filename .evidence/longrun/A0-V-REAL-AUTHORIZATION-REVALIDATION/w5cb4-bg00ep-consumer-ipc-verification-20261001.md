# BG00EP 消费者私有IPC验证

基线AOS-001004/m1@4097df94。新增consumer_ipc，复用issuer Unix peer/listener/framing与JSON hooks；不重写OS身份或消费幂等状态机。wire固定schemaVersion/method/payload，只有inquiry/consume_once；配置和凭据仅可信进程参数。监听前要求外部OIDC配置、私有passfile/attempt目录、绝对socket路径与不同OS UID门。一个连接只分派一次，错误脱敏，响应失败不重发。

RED句柄97365缺模块exit2；首轮consumer/issuer IPC句柄35565：26 passed/4.26s/exit0。加真实kernel peer错配及响应发送失败后单次分派，累计句柄78153：**44 passed/17.75s/exit0**。

```sh
services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_network_consumer_ipc.py services/aos-api/tests/aip/test_aip_network_issuer_ipc.py services/aos-api/tests/aip/test_network_consumer_signed_https_pg.py services/aos-api/tests/aip/test_network_consumer_service_pg.py --tb=short --show-capture=no
```

真实Unix socket同UID/配置API UID与kernel peer错配均在业务前拒绝。重复JSON键、bool schema、NaN、超长、wire自报UID/DSN/actor/目录拒绝。路由与发送错误单元测试使用明确peer替身，仅证明单次分派/脱敏，不代表真实跨UID授权成功。HTTPS+PG累计保持真实签名和数据库验证；未创建正式OS用户、HBA、listener或当前业务数据。

复审风险：共用read_issuer_frame现为逐recv 5秒超时，64KiB帧虽有限，慢速分片可延长整体读取；尚无整帧截止时间保证。BG00EQ须优先同一transport最小修复并真实socket慢速测试，不在此宣称总时限或正式IPC验收。正式独立UID/凭据ACL/外部身份与部署、首链仍pending；本波不启动daemon。原接口/代码不变，git diff --check exit0。

当前库继续只读118，代码122未部署；Host/worker/Provider关闭、不读商城源/旧Run、不手工run_definition、不push，230 L0挂起。下一波BG00EQ修共享整帧截止时间后再回正式启动前置与生命周期。
