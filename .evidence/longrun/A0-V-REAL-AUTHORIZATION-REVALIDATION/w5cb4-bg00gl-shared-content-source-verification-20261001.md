# BG00GL 共用当前内容来源准备段 verification

基线 AOS-001052 / m1 f8e04a02；2026-10-01。接续开工七强一致 CURRENT，memory-validate GREEN（1507 Delivery / 1506 Task / 4010 events）。

## 实现与复审

原 ContentBudgetCommandOwner._build_command 的审批前来源读取抽为 _prepare_sources；返回仅限同事务使用的当前来源，不含 approval，不调用额度消费 fence，不建立 claim/hold/Provider。原命令构造继续执行 _approved_action、_approved_bound 与 Host revalidate。GrowthPlan/Method 读取前移，失败仍禁 claim。未改 API、schema、claim/execute/unknown。

复习 231-5、GK 来源审计及 GL 文件方案；修改与方案一致。首生来源读取可脱离既存 Action，解除生产新批准的循环依赖；这不是正式首生 Proposal/checker 的实现。

## RED 与当前工作树 GREEN

历史本波 RED /tmp/aos-gl-red.log：缺 _prepare_sources 的两个参数分支失败，2 failed / 11 passed，退出1。首次 GREEN /tmp/aos-gl-regression.log：31 passed / 17.88s。

接续对当前文件重新运行（services/aos-api cwd）：

```sh
.venv/bin/python -m pytest -q tests/extension_runtime/test_ecommerce_content_budget_command_owner.py tests/aip/test_content_budget_risk_bound_pg.py tests/aip/test_content_first_action_budget_pg.py tests/aip/test_budget_configuration_runtime_pg.py --tb=short --show-capture=no
```

退出0，结果：31 passed, 7 warnings in 17.27s。输出 /tmp/aos-gl-resume-regression.log。既有7条警告为Pydantic字段命名与Starlette/httpx弃用提示。

两个源码 compileall 及精确 git diff --check 退出0。Owner 的数字/风险组合测试含替身，仅证明来源提取与原接线；相邻真实 PostgreSQL 测试使用隔离测试库，证明各自预算/拒绝合同，不代表当前正式实例或全来源自然链。无UI变更，browser不适用。

## 当前文件 SHA256

- services/aos-api/aos_api/ecommerce_content_budget_command_owner.py: `0add1249c5f20a5cf8bc2d662eb991fa2b8a4bf51020147f898a0da0e4eb4a8a`
- services/aos-api/tests/extension_runtime/test_ecommerce_content_budget_command_owner.py: `43ad46411c57e342390f6106f9a20f9d918634e7e3a2b6f3b09ddbfc6ec5fedc`

## 未完成与下一波

BG00GM：共用来源基础上的显式首生合同、正式身份入口、当前metadata/member/markings/预算/来源核验、不可变Draft绑定及独立checker，最终合法来源到held。通用开发Principal不得成为正式权威；RETURN和generic ProductionContext门不放宽。不新建影子审批系统。

当前真实库未连接或写入，无迁移、服务重启、商城源读取、旧12Run重放、手工run_definition、Provider调用；未更改运行门控。正式首链、八工作台真实场景及观察发布均未完成。Watchdog方案未部署。m1精确提交、不push，其他既有dirty保护。
