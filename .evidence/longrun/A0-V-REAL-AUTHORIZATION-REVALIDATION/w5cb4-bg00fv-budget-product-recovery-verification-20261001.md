# BG00FV 私有预算签发客户端与产品原请求恢复 verification

基线 AOS-001036 / m1@3d63e469；Task W5CB4-BG00FV-20261001。当前库和既有用户dirty保持不动。

## 验证记录
- 首RED：新client模块不存在，pytest test_budget_cost_client.py exit2/0.40s。
- 首3文件：48passed/1failed/31.42s；唯一失败为client测试使用pytest长路径触发103bytes限制。改为/tmp下随机短且不存在socket路径，生产门不放宽。
- 累计命令：`services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_budget_cost_client.py services/aos-api/tests/aip/test_budget_cost_product_pg.py services/aos-api/tests/aip/test_budget_activation_product_pg.py services/aos-api/tests/aip/test_budget_cost_process.py services/aos-api/tests/aip/test_budget_cost_preflight_pg.py services/aos-api/tests/aip/test_budget_cost_issuer_pg.py services/aos-api/tests/aip/test_network_issuer_client.py --tb=short --show-capture=no` → 112passed/7warnings/49.95s/exit0。
- 补maker撤销刷新与错身份零写零发送两项：test_budget_cost_product_pg.py 15passed/7warnings/16.84s/exit0。与112有重叠不相加；本波新14client+15product用例。
- compileall五实现/两测试、git diff --check exit0；alembic heads a0v_125/exit0，无新迁移。临时输出/tmp/aos-fv-{red,green,regression,final-targeted}.log。

## 功能与复审
- client固定短绝对socket/独立API与issuer身份，复用private transport核内核peer才发送。一次execute_once/inquiry帧，64KiB，strict响应键/类型/状态/decision/hash/ref/eligiblefalse；异常/截断不重发。真实socketpair单帧及错误kernelpeer零发送测试；不是正式跨UID正向部署。
- 新预算费用产品POST/GET `/v1/aip/budgets/cost-proposals/{proposal_id}/review-requests/{operation}`。POST仅hash+决定或撤销理由，GET仅安全ref。必须private JSON AOS_BUDGET_COST_API_CONFIG，精确键集合无数据库凭据/默认回退；配置缺失/extra database 503。
- 外部OIDC/current成员每次验证；slot固定scope/actor/operation/proposal，保存原body/hash/key/actor<=4096不含JWT，0600/O_EXCL/fsync后至多派发一次。重复POST或刷新GET只Inquiry，body变更409；损坏/hash漂移/权限/symlink/FIFO一律拒绝，不能当不存在重开。fsync前后故障保留slot；未提交unknown0行、已提交unknown回读1行；并发只有一次execute，maker撤销也可刷新回读。
- 实际产品PG/TLSJWT证明通过transport适配到FU真实issuer登录/Schema/签发核心，未替换Principal/DB/Receipt；适配本身不是正式独立OS端到端证明。客户端真实内核拒绝另测。HTTP为隔离ASGI+真实JWT/PG，不是当前8080上线。
- 原budget activation product仅抽出原子创建小函数，共享代码鉴权/envelope/回读/冲突/dispatch流程不变；其全部22项PG回归通过。共享API从不直连预算issuer数据库，读取当前membership用既有read-only路径。
- 无UI修改/当前服务重启，浏览器不适用；无商城源/旧12Run/手工Run/230L0，不启Host/worker/Provider，不push。当前真库零连接/零写/零迁移，首链仍未完成。

## 下一波
BG00FW审核UI/原请求刷新恢复与适用浏览器禁入验收；再受限consumer同事务复验当前批准/撤销/head/source并激活+唯一Receipt。正式OS/OIDC/凭据/launch配置、当前实例最新代码安全迁移仍独立备份克隆零窗口；代码125不能代表当前库版本。Goal继续active；防停工只交付方案、未部署。

复审追加：首个成功后多余inquiry RED为1failed（/tmp/aos-fv-single-response-red.log），实际观测execute_once+inquiry两次调用。FU已从不可变Receipt读回且client严格验响应，产品改为直接保留observed以适配有限一次连接进程；unknown仍Inquiry，重复请求不重发。最终client+product复验见下述结果。

最终结果：`pytest -q test_budget_cost_client.py test_budget_cost_product_pg.py --tb=short --show-capture=no`（上述services路径）29passed/7warnings/16.57s/exit0；/tmp/aos-fv-final-client-product.log。末次compileall/diff check退出0。
