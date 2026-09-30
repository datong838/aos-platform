# BG00FD verification · 2026-10-01

## 范围 / 结果
m1起点72f0ca1c、authority AOS-001018。仅网络提案创建响应丢失后的精确只读查询；未部署当前真实实例。当前E16禁入/E17首链pending未改变。

## 命令与新鲜输出
1. `scripts/memory/memory-status --json`：strong AOS/Prime CURRENT，eventual个人笔记STALE已知warning；exit0。`memory-validate --json`：GREEN、1472 deliveries/1470 tasks/3903 events；exit0（本波Task之前）。
2. RED：`services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_network_proposal_reconcile_pg.py --tb=short --show-capture=no`：缺proposal_request_hash ImportError，exit2；不是通过。
3. 最小实现后同命令：14 passed/10.67s/exit0。随后增加未提交事务用例。
4. 累计（最终15项新专项包含其中）：
```sh
services/aos-api/.venv/bin/python -m pytest -q   services/aos-api/tests/aip/test_network_proposal_reconcile_pg.py   services/aos-api/tests/aip/test_network_issuer_application.py   services/aos-api/tests/aip/test_network_consumer_application.py   services/aos-api/tests/aip/test_network_atomic_consumer_pg.py   services/aos-api/tests/aip/test_aip_network_policy_action_producer.py   --tb=short --show-capture=no
```
结果65 passed/36.90s/exit0；7个既有pydantic/Starlette warnings。
5. `git diff --check` exit0；逐项review本波diff与新模块，旧request hash公式不变、producer仍走同guard、无迁移/真实库写/Host启动/商城源/旧Run重放。

## 证据覆盖与限度
- pytest自动临时aos_test_*_ti4_test库，fixture先断言不是共享库；真实PG迁移与producer/issuer历史测试夹具。不是正式IdP/真实账号或真实链通过。
- 新API真实HTTPS JWKS/RSA JWT，经require_principal、原producer创建，再仅用原key/body查询。DNS/CA是隔离测试布置；没有mock审批业务服务。数据库故障用替身仅证明503脱敏，非可用性证据。
- readonly/repeatable-read实际SHOW通过，wrongscope/writeable连接拒绝。重复查询、改变原candidate/expiry/version、跨maker/canarytenant、unknown key、body身份注入均按合同拒绝或待对账。
- 原事务未提交时unresolved，提交后observed同ID；没有调用第二次创建。原proposal到期且membership删除后历史创建仍可查回，不声明当前授权有效。
- Proposal/Draft/Event/Head/Revision/Receipt前后计数相等；新查询无业务写。
- 新endpoint的observed只表示历史创建，unresolved不能证明未执行，conflict不含ID，DBerror503不能当unresolved。
- 本波无UI变更，未运行浏览器且不声明浏览器通过。API创建请求仍要求调用者保留原key/body；跨页面持久请求恢复与产品接线留BG00FE。
- 现有正式OS/OIDC材料、受限API部署、a0v118→122恢复波、八配置Owner/Host、自然首链均未由本波证明。Goal保障方案也未实施。

## 下一波
BG00FE复用现有审批收件箱与API transport接入网络decision-attempt/inquiry与创建查询；先复核持久请求引用及browser-pilot可用路径，不写客户端审批权威、不手工消费或Run。
