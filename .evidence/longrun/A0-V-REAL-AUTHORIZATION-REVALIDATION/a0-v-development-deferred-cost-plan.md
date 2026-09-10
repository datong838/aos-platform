# 开发验收费用延后核算：实际依赖对账与施工卡

用户已明确开发、自测、接单验收不考虑成本，商业使用再核算。该授权直接作为本切片范围依据，不再索取价格。目标是继续真实业务链，同时区分执行完成与费用结清；不是把未知费用写成零。

## 当前代码证据

| 实际位置 | 当前约束 | 必须处理的行为 |
| --- | --- | --- |
| services/aos-api/aos_api/aip_model_runtime_contracts.py / ModelPriceSnapshotRevision | 至少一个数值单价 | 明确开发未核价记录；旧价格正文与 hash 不漂移 |
| services/aos-api/aos_api/aip_model_governance_policy_contracts.py / BudgetPolicyRevisionCreate | unknown_price_behavior 只能 block | 开发 opt-in 绑定独立授权、租户、模型、有效期；商业缺省仍 block |
| services/aos-api/aos_api/aip_model_runtime_resolver.py / _candidate | READY 必须有有效 price ref | 识别明确未核价授权；缺失记录不能自动豁免 |
| services/aos-api/aos_api/aip_exact_provider_invoker.py | 执行前 exact 政策回读 | 在 Secret/transport 前重新核验开发授权，无隐式绕过 |
| services/aos-api/aos_api/aip_responsibility_profile_store.py / projected costs | 已支持 unknownCodes 和空金额 | 保留 unknown，开发冻结不得把金额未知变成执行不可能；仍验证角色、能力、来源和责任 |
| services/aos-api/aos_api/aip_budget_reservation_store.py / settle、_actual_from_usage | 结算必须得到整数 actual_minor，输入输出逐项单价 | 新增费用待核算状态，实测 UsageReceipt 继续引用，不能伪造 settled=0 |
| services/aos-api/alembic/versions/ar2_003_ecommerce_budget_reservation.py | SQL 状态机和结算表强制非空金额 | 新增前向迁移配合费用待核算状态，不能只改 Python 枚举 |

以上核查改变施工顺序：先打通合同与 SQL 状态机，再登记 active Model/Route。若先发布一个空价格模型，会在实际结算失败并卡住业务恢复，不能视为完成。

## 分步实施与退出

1. 明确开发执行授权合同：固定 scope、exact Provider/model 和批准事实、有效期。授权的含义仅为承担开发调用费用，不声明价格。沿用既有策略 Revision Owner，不新建平行审批库。新增字段必须仅在 opt-in 时序列化，保持旧不可变 payload hash。
2. 模型及策略合同支持明确 deferred 状态；商业默认及缺授权负例仍拒绝。开发用量质量始终 measured，金额 unknown，不能转成 estimated=0。
3. 预算状态机新增 execution-complete/cost-pending 语义，保留 UsageReceipt 与调用幂等键；SQL/Python/事件投影同步，费用后核算只结账，不重新调用 Provider。租户隔离、恢复、重复结算及撤销测试必须覆盖。
4. 接入 Resolver/Invoker 和责任计划；租户、模型、到期或批准引用漂移在调用前拒绝。能力和业务审批依然独立，媒体长任务仍按原任务查询。
5. 使用已完成的三样本证据建立正式 Eval 对象，再发布真实模型/文本路由，核实实例及首链。此处不得把固定文本样本 Gate 扩张为 speech/video 能力。

测试文件主要为 services/aos-api/tests/aip 下 test_aip_model_runtime_contracts.py、test_aip_model_runtime_resolver.py、test_aip_budget_reservation_contracts.py、test_aip_budget_reservation_pg.py、test_w6_02_responsibility_profiles.py，新增对应开发授权专项测试。隔离迁移验证先于实际恢复库升级，原库/卷保留；回滚为禁用开发策略，不回写已产生的 receipt。

## 本次核查边界

只读源码对账，无真实调用、无 DB mutation、未改变商业预算约束。上一轮 17d81aa9 三样本结果仍是模型合同证据；整个 A0-V 和首链未完成。执行主线继续，不等待报价。
