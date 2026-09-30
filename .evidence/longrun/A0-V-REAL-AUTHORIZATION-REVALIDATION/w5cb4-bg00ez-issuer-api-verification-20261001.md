# BG00EZ verification — 2026-10-01

## 实现与方案复审
新增issuer application，用认证Principal构造精确租户请求并复验外部JWT及subject/scope。复用reserve_decision_attempt；consumer既有先记录再单发/重复与未知转inquiry的流程提取为aip_private_dispatch，两个调用方共享。API记录归API独立0700目录，不含Bearer；冲突409、配置或记录失败503、身份403；发送异常unresolved，保留记录。

新增POST /v1/aip/runtime-guard-policies/networks/activation-proposals/{proposal_id}/decision-attempts及/inquiry，使用既有DecideActionProposalRequest/Idempotency-Key。查询的决定体仅形成精确request_hash，服务端只读对账。旧decision的ActionDraftBundle合同及无issuer时的禁入保留；本波不是新审批权威。

AOS_NETWORK_ISSUER_API_CONFIG读取既有私有JSON函数，仅endpoint与API attempt目录；缺失None，显式错误固定拒绝。main lifespan新增4行，在原runtime body前加载、finally清空，不开启独立issuer/Host或连接DB/socket。与方案一致，未改当前.env/实例/库/前端。

## 测试证据
RED session72857：application/startup缺模块，exit2/0.43s。初次专项与消费者相邻session28206：40 passed/12.10s/exit0。补充真实权限漂移与注入磁盘失败后，累计session21168：114 passed/26.30s/exit0，7已有warning。git diff --check exit0。

```sh
services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_network_issuer_application.py services/aos-api/tests/aip/test_network_issuer_startup.py services/aos-api/tests/aip/test_network_issuer_client.py services/aos-api/tests/aip/test_network_consumer_application.py services/aos-api/tests/aip/test_network_consumer_startup.py services/aos-api/tests/aip/test_network_consumer_client.py services/aos-api/tests/aip/test_aip_network_issuer_attempt.py services/aos-api/tests/aip/test_aip_network_issuer_auth.py services/aos-api/tests/aip/test_aip_network_policy_action_producer.py services/aos-api/tests/test_health.py services/aos-api/tests/aip/test_aip_provider_health_main_startup.py --tb=short --show-capture=no
```

真实临时文件+TLS/JWT+HTTP测试证明身份重验、一次Command后重复/显式/破损记录仅Inquiry、重新构造配置读取既有记录、冲突/身份/权限/存储失败不发送、body注入拒绝、默认503。IPC capture与生命周期body/cleanup替身只证装配/分发，不证明正式签发或部署。隔离HTTP fixture只写临时测试库组织工作区；当前真库零写。无UI变更，不声称浏览器验收。

## 未完成与下一波
rg定位serve_one_issuer_connection/open_private_issuer_listener目前仅组件及测试调用，仍缺独立生产进程装配。BG00FA复习现有消费者有界进程与issuer连接，先方案/RED，补精确issuer配置及有界进程入口；复用监听生命周期，不复制签发权威。不借此造正式OS账户/OIDC或启当前Host。
正式OS/OIDC材料、代码119–122与当前118差距、损坏启动载体仍需独立恢复/部署波。正式Event、策略激活、八配置/Owner/Host与自然首链未完成；旧Run/商城源/manual run_definition/Provider/230L0不触碰。不push。
