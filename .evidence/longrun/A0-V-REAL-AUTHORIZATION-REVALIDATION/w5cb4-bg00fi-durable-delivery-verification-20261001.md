# BG00FI verification · 2026-10-01

基线 m1@c1c86169 / AOS-001023；Task W5CB4-BG00FI-20261001。新批准事件持久投递基础，不开启自然消费。

## 执行与结果
- 开工 memory-status 强一致 AOS/Prime CURRENT；memory-validate GREEN（1478 deliveries/1477 tasks/3921 events）；个人 eventual 笔记 STALE 为既有 warning。
- RED复现：`services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_network_approval_delivery_pg.py --tb=short --show-capture=no`：4 failed/4.75s/exit1，表/函数缺失。实现后同命令4 passed/4.98s/exit0。
- 补事务回滚、并发事务SKIP LOCKED、撤销maker及caller直写拒绝后，专项7项纳入累计：
```sh
services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_network_approval_delivery_pg.py services/aos-api/tests/aip/test_network_consumer_boundary_pg.py services/aos-api/tests/aip/test_network_approval_event_driver_pg.py services/aos-api/tests/aip/test_network_consumer_actor_pg.py services/aos-api/tests/aip/test_network_atomic_consumer_pg.py services/aos-api/tests/aip/test_network_proposal_product_pg.py --tb=short --show-capture=no
```
结果65 passed/32.89s/exit0，7个既有Pydantic/Starlette warning。日志/tmp/aos-bg00fi-pytest.log仅辅助，本文件保留命令结果。
- services/aos-api下`.venv/bin/alembic heads`：a0v_123 (head)，exit0。没有对当前实例执行upgrade。
- `git diff --check` exit0。无UI改动，无新增浏览器通过声明。

## 方案/代码复审
1. a0v123仅为未来新network approved事件同事务INSERT投递；无历史回填、无外部调用、无自动worker注册。原Action outbox执行租约合同不变。
2. 专用表由迁移owner持有，FORCE RLS/双scope；consumer_owner仅SELECT/INSERT及六个状态列UPDATE；API/runtime/issuer/caller无直接写。边界测试枚举全public列权限，只有明确新增六列被允许。
3. claim固定30秒UUID token，精确原maker当前member、角色旗标/成员关系/GUC验证，单行SKIP LOCKED；pending首次dispatch，过期claim/unknown只inquiry。回滚认领未派发命令，后续才仍是首次dispatch。
4. finish检查原maker/token/期限，查询不可变原消费Receipt，并用既有a0v120 canonical hash校验tenant/proposal/event/target/binding及精确result refs。无Receipt变unknown并延迟30秒，不接受客户端success标志。原a0v121只读事务查询函数不在写事务中误用；此处不授予执行权。
5. 事务失败测试在独立PG的投递AFTER INSERT触发器注入真实异常，批准和投递计数均不增加；finally移除测试触发器。不是当前实例故障注入。
6. Receipt确认正例通过原受限consumer SQL真实写head/revision/Receipt。测试显式调用consumer以验证确认合同，不代表inquiry获准重发或生产自然首链已通过。

## 未完成与边界
当前真实库未写/迁移/重启；最后实测a0v118仅为此前现场，未重新声称当前健康。代码头123，后续正式恢复波须备份、克隆118到123全链演练、零执行窗口。
生产轮询、原maker合法服务身份、外部OIDC/OS配置、API载体修复、八配置/Owner/Host/自然首链仍pending。Host/worker/Provider未开启，无商城源读取/旧12Run/手工Run/230 L0动作。Goal保障方案未实施，Goal状态未改。

## 下一波BG00FJ
在正式身份边界内接有界单次claim→原事件driver→精确finish；dispatch/inquiry必须从持久认领模式决定，过期unknown不能被旧driver默认Command掩盖。先审现有consumer IPC与身份配置，再方案/RED；不保存人类JWT、不以checker或共享API主体冒充maker，不注册默认生产后台。
