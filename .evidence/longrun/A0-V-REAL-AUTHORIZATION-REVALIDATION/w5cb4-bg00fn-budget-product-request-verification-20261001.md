# BG00FN verification · 2026-10-01

基线AOS-001028 / m1@39e6a883；Task W5CB4-BG00FN-20261001。

## 验证命令与结果
RED专项 `services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_budget_activation_product_pg.py --tb=short --show-capture=no`，3errors/4.42s/exit1，模块尚不存在；实现后三操作原提交响应丢失/重载专项3passed/6.49s/exit0。

最终累计：
```sh
services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_budget_activation_product_pg.py services/aos-api/tests/aip/test_budget_review_inquiry_pg.py services/aos-api/tests/aip/test_budget_preview_inquiry_pg.py services/aos-api/tests/aip/test_aip_budget_activation_store_pg.py services/aos-api/tests/aip/test_aip_budget_api.py --tb=short --show-capture=no
```
58passed/44.82s/exit0（含新22项）；7既有warning；git diff --check exit0。

## 方案/代码复审
1. 新产品层使用独立AOS_BUDGET_REQUEST_DIRECTORY，无默认临时目录、无自动mkdir；绝对路径、0700/owner校验，复用已验证marker读取的0600/NOFOLLOW/普通文件/4096上限。目录缺失或文件损坏503，不能当not_attempted。正式部署不得切换空目录，需备份恢复一致性。
2. 每次重验外部TLS签名OIDC及scope/subject，与原Principal一致；当前owner/admin先于文件读取。原Store继续精确maker/checker校验。JWT仅内存验证，不落marker/Receipt/日志。
3. slot绑定scope+actor+operation+稳定source；preview固定budget/revision/head、decision固定preview、revoke固定decision，可变审批/原因/target不进入slot。原body完整留存+hash复验，输入漂移409，不因换body产生新key。
4. O_EXCL独占；完整写+file fsync+directory fsync后仅一次调用原Store。已有slot只inquiry，未知异常保留slot，无删除/覆盖/自动重发。文件尚未写完时并发读取失败关闭503，不能抢发。PG仍唯一预算/批准/撤销事实；marker不是权限。
5. GET只带安全source引用，服务端还原原body/key，不回body/reason/token；not_attempted仅该产品槽未记录，不推断数据库不存在。observed复用FL/FM最小ID+activationEligible=false；已批准仍不代表active预算。原API保留，static intent GET优先于preview动态id路径。
6. 新22项实际隔离PG/TLS JWT，三操作真实创建后响应丢失，重复POST/刷新只查询、Receipt计数仅增一次；输入漂移、当前成员撤销、跨身份/scope、并发单调用、文件/目录fsync失败、调用前失败、损坏/hash/actor/权限/symlink/FIFO、HTTP GET不依赖原body与配置缺失503。故障注入不当正式业务证明。
7. 未改旧BudgetRevisionSetupPanel的draft写路径；其刷新原请求恢复缺口仍在，不能宣称已修。当前完成的是activation review产品后端合同，BG00FO接前端预览/复核/撤销表单与引用恢复。

## 风险与下一波
无新migration/当前真库写/生产重启/UI修改/浏览器通过声明。代码a0v123，最后真实库118是旧现场，118→123独立安全恢复仍待；Host/worker/Provider未启，商城源/旧12Run/手工Run/230 L0未动，不push。
BG00FO接原预算配置页的activation review产品表单，服务端保留原请求、URL仅安全引用，不localStorage权威、不离线写队列、不未知结果重发。正式外部OIDC/目录部署、外部usage/原子激活、八配置Owner、自然首链仍pending。Goal状态未改，看护保障方案未部署。
