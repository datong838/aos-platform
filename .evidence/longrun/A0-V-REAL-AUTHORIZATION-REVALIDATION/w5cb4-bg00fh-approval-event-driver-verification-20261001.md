# BG00FH verification · 2026-10-01

m1@c71bb722/AOS-001022，Task W5CB4-BG00FH-20261001。一个精确持久批准事件处理器，不注册后台轮询或新增HTTP入口。

## 命令和结果
- memory-status强一致AOS/Prime CURRENT；memory-validate GREEN（1477 deliveries/1475 tasks/3917 events，Task前），exit0；eventual个人笔记STALE已知warning。
- RED：`services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_network_approval_event_driver_pg.py --tb=short --show-capture=no` 缺模块，exit2。首次实现误放services/aos-api/顶层，仍ImportError；核对新文件内容后移至计划aos_api/目录，没有覆盖既有文件。
- 移正后专项8 passed/9.92s/exit0；补真实消费服务/PG Receipt组合用例后最终9项纳入累计：
```sh
services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_network_approval_event_driver_pg.py services/aos-api/tests/aip/test_network_consumer_application.py services/aos-api/tests/aip/test_network_consumer_actor_pg.py services/aos-api/tests/aip/test_network_atomic_consumer_pg.py services/aos-api/tests/aip/test_network_consumer_signed_https_pg.py --tb=short --show-capture=no
```
56 passed/31.65s/exit0，7个既有Pydantic/Starlette warning。
- `git diff --check` exit0；新处理器/测试与方案复审通过。本波无UI/前端变更，不重复前端回归、不新增浏览器通过声明。

## 证据边界
1. 首先验证当前ConsumerApplicationConfig和外部OIDC实际JWT签名/scope/subject；没有JWT持久化，也不把checker身份替换为maker。
2. 连接必须aos_runtime、正确双租户GUC、readonly/repeatable-read；按proposal+event精确JOIN读取，要求网络动作、approved checker.1、独立checker、原maker当前member、事件hash/binding一致。消费refs来自数据库而非通知payload。
3. 关闭读取连接后才进入原execute_consumer；独立服务和PG事务继续进行完整时效/成员/目标/fence校验。驱动器不复制完整批准权威，也不把通知当授权。
4. 重复事件得到Command→Inquiry；不同maker/checker/不存在event/跨租户/过期或不符JWT均不派发、不落attempt。可写读取连接503。
5. 组合用例用真实TLS/JWT、隔离PG、受限consumer DB角色及原子函数生成真实Receipt；IPC transport以原服务函数桥接（不是实际Unix socket），提交后抛响应丢失，第二次同事件只Inquiry查回原Receipt；head/revision/receipt均为1。不是正式账号、正式安装或自然订阅通过。
6. 其余IPC capture仅证明精确ref与调用合同，不作实际策略生效证据；业务测试库aos_test_*_ti4_test独立，不是当前真实库。

## 尚未闭合
现有持久approval_event/action_event已写，但可靠后台订阅/ack、原maker合法服务身份来源、正式部署与自然消费尚未接通；函数当前没有生产调用入口。不复制或后台保存人类JWT，不使用checker JWT/共享API主体绕过a0v122。
当前真实库只读、未迁移/重启，Host/worker/Provider未启，无商城源/旧12Run/手工Run/230 L0变化。正式身份、API载体修复、118到122恢复波、八配置Owner/Host和自然首链仍pending。Goal保障方案未实施，Goal状态未变。

## 下一波BG00FI
先检查现有事件投递/outbox/ack与身份供应合同，制定可靠订阅及有界消费方案；任何新迁移先独立测试/克隆，禁止当前真库写。当前单事件处理器不是自动链完成证据；未明外部结果只读对账。
