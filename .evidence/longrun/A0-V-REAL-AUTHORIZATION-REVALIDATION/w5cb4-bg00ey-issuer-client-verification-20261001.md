# BG00EY verification — 2026-10-01

## 实现和复审
从consumer client提取原0750目录/0660socket及service UID/GID检查、Unix stream内核peer准入到aip_private_service_transport；原消费者Endpoint/响应/错误及一次发送行为保留。新增IssuerEndpoint与request_issuer，对exact Command/Inquiry一次发送，复用issuer帧读取、重复键及NaN拒绝。连接身份验证先于JWT发送。任何已发送后的丢包/坏响应/关闭异常返回unresolved，无重连。observed必须eventId合法、approved/rejected；Command还要求决定一致。非observed不接受事件信息；blocked只接受固定错误。

与方案一致：未复制签发/审批/租户/哈希数据库权威，仍由已有issuer service/readonly reconcile处理。没有HTTP接线、启动或正式身份配置；裸传输不负责跨调用防重，下波API持久attempt必须补齐后才接产品。没有改当前实例或数据。真实socketpair证明帧，与既有decode_issuer_request双向兼容并保留request_hash；不证明跨OS身份正向。无UI改动，无浏览器验收声明。

## 可复核测试
RED session49476：缺issuer_client模块，exit2，0.41s。初次两个客户端专项session48052：31 passed/4.54s/exit0。追加approved/rejected及既有服务端解码互操作后累计session60469：90 passed/3 skipped/7.65s/exit0，7已有warnings。

```sh
services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_network_issuer_client.py services/aos-api/tests/aip/test_network_consumer_client.py services/aos-api/tests/aip/test_aip_network_issuer_contracts.py services/aos-api/tests/aip/test_aip_network_issuer_ipc.py services/aos-api/tests/aip/test_aip_network_issuer_service.py services/aos-api/tests/aip/test_aip_network_issuer_attempt.py services/aos-api/tests/aip/test_aip_network_issuer_reconcile.py services/aos-api/tests/aip/test_network_consumer_application.py services/aos-api/tests/aip/test_network_consumer_startup.py --tb=short --show-capture=no
```

3项跳过来自issuer service两项/reconcile一项，要求显式隔离issuer proof目录；没有将跳过计为PG真实通过。应用/生命周期替身测试仅证代码逻辑。git diff --check exit0。此前已确认强一致投影CURRENT及memory-validate GREEN，AOS001013。

## 剩余/下一波
BG00EZ：API侧issuer持久attempt与产品决定/只读查询入口，复用现有认证/attempt，不直连签发数据库；重复/未知只能inquiry。正式OIDC/OS材料待提供；当前库118与代码119–122差距、启动载体异常须独立部署恢复波。真实批准、八配置、Owner/Host及自然首链尚未证明。保持真实库只读、无商城源/旧Run/manual run_definition/Provider，不push。
