# BG00EW verification — 2026-10-01

## 实现
新增API应用配置/适配；配置由app.state持有默认None，不接受body注入。References抽出公共字段验证，原Command/Inquiry继承；token/scope仍独立，旧hash合同测试通过。认证头parse_bearer→真实外部OIDC再验证→subject/scope比对；持久attempt复用旧0600/O_EXCL/fsync机制，API自有0700绝对目录。首次Command，Already/Unknown仅Inquiry，Conflict409。未配置503，身份403，unknown202，observed200，服务拒绝403。无消费重试或DB fallback。

## 验证时间线
- session45502 RED缺References，收集exit2/0.41s。
- session31486 应用+合同30 passed/11.06s/exit0。
- session97572 累计58 passed/10 failed/45.01s/exit1：HTTP预期422与既有400不符；9个签名PG失败因通用client fixture清除正式meta_object_type。
- 定位conftest.py的DELETE FROM meta_object_type；新HTTP测试改独立FastAPI/router/真实认证/既有错误handler，避免清库fixture；不修改生产准入，不重建正式业务元数据。
- session25566 最终68 passed/38.09s/exit0，7已有warning。

```sh
services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_network_consumer_application.py services/aos-api/tests/aip/test_network_consumer_contracts.py services/aos-api/tests/aip/test_network_consumer_client.py services/aos-api/tests/aip/test_network_consumer_attempt.py services/aos-api/tests/aip/test_network_consumer_signed_https_pg.py services/aos-api/tests/aip/test_aip_runtime_guard_policy_api.py --tb=short --show-capture=no
```

真实临时TLS/JWT及私有文件，HTTP真实require_principal/外部认证；IPC用捕获替身仅证明应用分派与不重发，不是正式业务验收。原实际socket与签名PG同波回归。HTTP未知返回202，第二消费和独立查询都是Inquiry，token不进attempt；body身份/路径字段拒绝。旧runtime guard API相邻通过。无UI变动，不作browser通过主张。

## 复审/边界
server-owned typed endpoint不可由HTTP指定；实际客户端仍kernel peer核验，消费者仍JWT/current actor/approval重验。未配置默认失败关闭；API侧和consumer側attempt由不同OS owner目录隔离；未对当前实例安装配置。真实库118只读，119–122未部署，首链未完成。启动载体异常仍单列恢复门。

## 下一波
BG00EX：正式API侧配置载体/启动注入方案与实现，复用私有文件校验，默认无配置，无凭据参数/请求注入；生命周期只装配客户端、不启动消费者或Host。仍需独立OS/IdP/ACL与部署证明。m1精确提交，不push，不读商城源/旧Run，不手工run_definition，230 L0挂起。
