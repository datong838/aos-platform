# BG00EV verification — 2026-10-01

## RED / GREEN
缺模块RED session27771：收集退出2，0.41s。实现后专项session20967：17 passed/4.29s/exit0。复审后累计session80895：66 passed/20.98s/exit0，7已有warning。

```sh
services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_network_consumer_client.py services/aos-api/tests/aip/test_network_consumer_contracts.py services/aos-api/tests/aip/test_network_consumer_ipc.py services/aos-api/tests/aip/test_network_ipc_deadline.py services/aos-api/tests/aip/test_network_consumer_signed_https_pg.py --tb=short --show-capture=no
```

## 覆盖与复审
真实socketpair合同：一次帧发送、JWT只进wire、Command/Inquiry方法不同、Receipt精确返回、响应丢失unresolved、无第二发送。JSON schema/重复键/NaN/额外字段、Proposal/contentHash漂移、bool revision、空Receipt拒绝；独立server kernel peer不匹配时socket没有发送数据。同UIDEndpoint拒绝；缺socket固定错误。
客户端只接受私有Endpoint与精确请求类型；连接前路径/owner/group/mode，连接后内核peer后才发送。connect/send各5s，读复用5s整体帧deadline/64KiB，没有reconnect/retry。发送后包括关闭异常都返回unresolved，不误分类成发送前Blocked。响应不宣称current active；客户端无DB凭据。实现与120 SQL result_ref七字段核对一致。

正向传输测试直接验证内部_exchange，不能替代完整不同OS UID正向request_consumer部署验收；签名HTTPS/PG测试为已有隔离业务回归，与新客户端不是当前真实安装全链。未伪造OS权限验收；未调用当前实例，未新增HTTP/UI入口，因此browser不适用。

## 未完成/下波
正式OS/IdP/ACL、当前库119–122迁移、安全启动载体修复、API应用接线和自然首链仍待证。BG00EW先做服务端配置持有的消费者应用适配：Bearer来自HTTP认证头、scope来自已验证Principal、exact请求引用，unknown只读对账，禁请求传endpoint/凭据。先计划/RED，默认未配置失败关闭，不启当前消费者。真实库只读、Host/worker/Provider不启、不读商城源/旧Run/manual run_definition、不push。
