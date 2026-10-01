# BG00GK 当前来源审计证据

2026-10-01，m1 c7b670af，AOS-001051。开工memory-status七强一致CURRENT；validate GREEN 1506 Delivery/1504 Task/4004 events。仅文档与证据变更。

## 可复核的源码证据

以下命令在aos-platform运行均退出0：

```sh
rg -n 'PRODUCTION_CONTEXT_REQUIRED|PLAN_PRODUCTION_CONTEXT_MISMATCH' services/aos-api/aos_api/aip_production_contract_store.py
rg -n 'action_binding_hash = internal_binding|compute_action_binding_hash' services/aos-api/aos_api/aip_action_store.py
rg -n 'not proposal\["action_binding_hash"\]' services/aos-api/aos_api/aip_budget_reservation_store.py
```

输出位置：ProductionContractStore 5123/5149；ActionStore 628/676；BudgetReservationStore 1271。

对ContentTaskRunOwner AST读取CreatePlanRevisionRequest的risk字面键（321行）结果：

```json
["reviewReceiptRef", "responsibilityPlanRef", "externalPublicationAllowed", "providerInvocationAuthorized"]
```

没有productionContract。后续同函数直接approve_plan/create_run/start_run；不是一个可在执行后补写production context的草稿入口。_require_task_plan既拒缺Context，也拒不等于Plan pinned Context的引用。故444建议的通用Preview→Action路径不适用于当前自然Owner，需调整为复用现有内部Action绑定生产机制；不能放宽现有Preview门。

文件SHA256：

| 文件（services/aos-api/aos_api/） | SHA256 |
|---|---|
| ecommerce_content_taskrun_owner.py | 30ae61c338e7338938b05409bee0d3800c9ae486c289b7614e55bda7501d5f43 |
| ecommerce_content_budget_command_owner.py | 728439d3e916e8ee64977e75713be48da6237a7a6e6e154c56a7359ceb3f7082 |
| ecommerce_content_agentrun_owner.py | 4544ef686a8b55401e5134063d9acd23652f63bab5516996224a959b08ade52b |
| aip_action_store.py | 86c78eb98ed7459e45dbdbdcdbf0f2899341a5815e24e74df3daaa71fb967d71 |
| aip_production_contract_store.py | f5c6b38bc5c43d18dba4e79ee8bab8fdbe11257e2d122f6517bcf6d40cc5e94f |

## 复用与剩余风险

ContentAgentRunOwner._build_request已核原Review/Brief/Method、当前Plan/Run/assignment、Skill及ModelRoute；ContentBudgetCommandOwner._build_command继续核安装、容量、费用来源，但在其中要求既存Action批准。因此不能直接拿整个_build_command生成新Action，存在循环依赖。下一步先提取不依赖Action批准的同一来源准备段，再由原Owner和新首生Action生产者共用，避免复制校验。

详文件方案见w5cb4-bg00gk-first-action-source-plan-20261001.md。未实现新producer、未新增审批/hold、无运行实例变更。本波无业务代码，RED/累计/browser不适用；不沿用GJ的80 passed冒本波测试。来源、正式身份、自然首链仍未完成，Goal不变。
