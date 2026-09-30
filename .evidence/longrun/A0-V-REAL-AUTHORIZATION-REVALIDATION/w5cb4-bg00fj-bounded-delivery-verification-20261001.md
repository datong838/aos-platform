# BG00FJ verification · 2026-10-01

基线m1@938b72c2/AOS-001024，Task W5CB4-BG00FJ-20261001。范围：一次有界投递，不是生产后台启用。

## 验证命令/结果
- RED：`services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_network_approval_event_driver_pg.py -k durable_inquiry --tb=short --show-capture=no` exit1；旧driver不支持inquiry，无法承载持久只查询模式。
- 专项：`services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_network_delivery_driver_pg.py services/aos-api/tests/aip/test_network_approval_event_driver_pg.py services/aos-api/tests/aip/test_network_consumer_ipc.py services/aos-api/tests/aip/test_network_consumer_client.py --tb=short --show-capture=no` 60passed/23.01s/exit0。
- 累计（19文件）：`services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_network_consumer*.py services/aos-api/tests/aip/test_network_delivery_driver_pg.py services/aos-api/tests/aip/test_network_approval_event_driver_pg.py services/aos-api/tests/aip/test_network_approval_delivery_pg.py --tb=short --show-capture=no` 239passed/54.54s/exit0；7个既有Pydantic/Starlette warning。
- `git diff --check` exit0。无migration新增（仍a0v123），无UI变化或浏览器通过声明。

## 实现/方案复审
1. 新严格Claim/Finish/Lease合同拒绝caller actorId、DSN、successbool、非整型schema、非法token/mode/时间/布尔attempt；SecretStr隐藏JWT。旧Command/Inquiry哈希和字段不改，复用原scope/JWT校验。
2. API侧有界driver只接ConsumerApplicationConfig和当前原maker Principal/外部JWT，鉴权先于claim。数据库凭据不进API；独立consumer在原连接/role和函数owner/SECURITY DEFINER/ACL检查后执行a0v123。服务端生成claim UUID，退出事务并提交才返回认领。
3. 私有IPC新增claim_delivery/finish_delivery，仍须原peer UID门；一次send/严格frame和响应合同，无自动重连重发。finish不接受执行成功布尔值，仅数据库精确Receipt确认。
4. claim提供的inquiry显式传入原事件driver；本地marker为空也不能回退Command。迟到的过期lease同样只查询。事件driver仍读取原PG refs，消费者继续完整当前授权门。
5. 组合测试使用实际TLS/JWT、独立PG、受限consumer服务与真实Receipt；IPC在组合中以原服务函数桥接，明确不是正式跨UID/socket部署验收。另有socketpair实际帧一次发送及既有真实kernel peer拒绝测试。
6. Command执行后响应丢失，finish查原Receipt确认，head/revision/receipt各1；finish响应丢失也不第二次Command；claim响应丢失后过期，仅Inquiry，head/revision/receipt各0、本地marker仍空，状态unknown。该unknown不是新的执行许可。
7. 错误token/过期token/dev token在claim前拒绝；checker无法认领原maker投递。没有保存JWT、创建假身份、借checker/共享API主体冒充maker。

## 限制与下一波BG00FK
一次函数尚无生产调用入口/后台注册，也没有正式原maker身份供应。短期有效JWT必须由合法调用方提供，当前代码没有长期存储、刷新或委托实现，不能把这个输入参数当已解决自然订阅身份。
BG00FK先审正式OIDC/工作负载主体与原maker委托合同、现有启动接点；有合法来源才设计自然订阅，无来源仅阻断对应实例并转八配置独立研发。不可添吞失败循环或假token制造自然首链。
当前真库未写/迁移/重启（最后实测a0v118为旧现场，代码a0v123）；118到123独立备份/克隆/零执行恢复、正式OS/OIDC/API载体、八配置/Owner/Host/自然首链仍待证。Host/worker/Provider未开启；不读商城源/不旧12Run/不手工Run/230 L0挂起/不push。Goal回读active，未改状态；此前Goal保障方案尚未部署。
