# BG00GF 费用配置受限产品接线 verification

基线AOS-001046/9a011c5c，代码head a0v128未新增迁移。当前真实库未连接/写入/重启；所有PG验收走conftest新建独立测试库。

## 交付与复审
- BudgetConsumerRequest增加consume/configure受限枚举，默认consume；固定SQL函数映射，复用fresh OIDC身份核验、低权限连接、持久attempt及一次写后只读观察。configure单独domain及attempt namespace，既有consume hash/key/namespace不变。
- service与IPC client共用严格业务Receipt验证；拒绝跨operation Receipt、额外字段、错误类型/hash/布尔revision、伪activationEligible，以及非确定性price/policy ID或非1版本。当前DB函数仍独立核真实内容来源和完整hash。
- product仍唯一recover_private_product_request安全状态机，configure单独原请求key；无JWT落盘。新增POST/GET configuration-request，默认消费旧路由保持；no-store和unknown只读查询。
- 既有有限consumer process无需新进程/新权限，解析枚举并复用dispatch。新测试经真实wire JSON解码后调用dispatcher；内核跨UID传输未正向验收，transport适配器不当正式身份。
- 无UI改动，API-only未做浏览器业务验收；正式部署须协调API和consumer版本。未消费先到的配置请求在service不会生成attempt/配置；产品已持久发出的请求仍禁止重发，下一波UI需以已观察预算消费Receipt作为配置入口前置。

## RED/专项/累计与退出码
1. RED：新HTTP configuration-request GET为404，1 failed/5.58s，exit1，/tmp/aos-gf-red.log。
2. 最小实现+旧client专项24 passed/6.71s，exit0，/tmp/aos-gf-focused.log。
3. 初次旧相邻累计106 passed/62.56s，exit0，/tmp/aos-gf-regression.log。扩展测试写入首次使用错误相对目录，FileNotFoundError，未改文件；纠正路径后补测试，不掩盖该操作错误。
4. 扩展专项13 passed/22.99s，exit0，/tmp/aos-gf-expanded.log；随后补撤销前无slot与非法operation及真实wire解析。
5. 最终命令（cwd services/aos-api）：
`.venv/bin/python -m pytest -q tests/aip/test_budget_configuration_product_pg.py tests/aip/test_budget_consumer_service_pg.py tests/aip/test_budget_consumer_client.py tests/aip/test_budget_consumer_process.py tests/aip/test_budget_consumer_product_pg.py tests/aip/test_budget_cost_configuration_pg.py tests/aip/test_budget_consumer_connection_pg.py --tb=short --show-capture=no`
结果120 passed/82.31s，7已有warnings，exit0；/tmp/aos-gf-regression-final.log，原session52702已回读终态。新配置测试15项，HTTP→原请求→wire decode→dispatcher→低权限service→真实PG，包含提交前/后传输丢失、commit ACK丢失、并发、撤销历史、未消费source、伪签名/过期/错误actor/canary、损坏文件、原attempt及严格Receipt。
6. compileall改动4源文件/新测试和精确git diff --check，exit0。

## 未证明的真实业务
隔离Provider前置为fixture，无真实Provider请求、商城源/旧12Run/手工run_definition/230 L0动作；Host/worker未启。真实库版本未读回，代码128不等于当前运行版本；安装/首链/八场景/观察/发布仍pending。Watchdog未部署，Goal未修改，无push。
下一BG00GG接现有预算审核面板的费用配置入口及严格恢复，须先核已消费Receipt再开放首次操作；随后Model/Task风险联合证明与正式实例独立恢复波。
