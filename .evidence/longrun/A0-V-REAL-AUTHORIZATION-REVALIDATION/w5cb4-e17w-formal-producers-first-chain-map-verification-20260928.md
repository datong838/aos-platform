# W5CB4 E17-w｜当前正式供给链与首链必要集只读映射验证

## 当前权威实测

2026-09-28 17:02 CST，在 `m1@df525491` 以 `scripts/a0v_current_preview_http.py:preflight` 对当前签名 Receipt 做四包签名、内容哈希、安装与迁移预检，再以 `psycopg` 连接立即 `conn.read_only=True` 调用 `read_candidates(conn, TenantScope('org-org','dev-project'))`；命令退出 0。结果：`aos_current_preview_20260927@a0v_109`、安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813`、已发布签名包 4；八类当前有效候选 `responsibility_plans/runtime_policies/data_policies/egress_policies/network_policies/quota_policies/budget_policies/budgets` 均为 0，`allPresent=false`。查询只读且未读取商城源。E17-u 同一当前库 operation/binding/configuration/assignment/Action proposal/approval/receipt 为 0、Host identity 全库 0；没有新的正向权威替代它。

## 八类正式生产者与缺口

| 有效候选 | 正式写入口/条件 | 当前结论 |
|---|---|---|
| responsibility_plans | `routers/aip_production_contracts.py` create/revise/freeze，当前 head 必须 frozen | API/Store 存在；当前 0，尚无产品确认的当前责任方案 |
| runtime_policies | `routers/aip_model_runtime.py` `/policies`，当前 head 必须 active | API/Store 存在；当前 0，实际 Provider/route 不可据此启动 |
| data_policies、egress_policies | `routers/aip_runtime_guard_policies.py` `/data-classifications`、`/egress`，当前 active 且有效期内 | 租户/CAS/幂等入口存在；当前均 0 |
| network_policies | 同一 router `/networks`，当前 active 且有效期内 | 正式入口存在；当前 0 |
| quota_policies、budget_policies | `routers/aip_model_governance_policies.py` `/quotas`、`/budgets`，当前 active 且有效期内 | 租户/CAS/幂等入口存在；当前均 0；政策候选不等于预算批准 |
| budgets | `routers/aip_budgets.py` `/v1/aip/budgets`，当前 active 且有效期内 | Draft 可发布；active 在 Store 前固定 `AIP_BUDGET_ACTIVE_APPROVAL_REQUIRED` 422。`aip_budget_store.py` 有租户/CAS/幂等 Receipt，但公开精确审批消费尚未接入；当前 0 |

八类计数只用于配置引导，`runtime_configuration_candidates.py` 已声明不能绑定安装或授权运行；需另有当前精确配置 Receipt、安装 operation/binding、签名/三身份/Host Owner 和批准。`scripts/a0v_ecommerce_runtime_host_bootstrap.py` 是固定 2026-09-12 旧库/角色/Host ID 的旧生产脚本，不能对当前库运行；当前正式 Host identity/assignment 生产者缺口仍在。安装 preview maker/checker 不是运行或预算审批。

## 首链施工顺序与下一文件级任务

231-3 的正式安装/运行 fence、231-5 的同代次同数据截面分析→内容→人工审批后自动续跑及 231-9 BG-00 四源产品恢复优先。先逐类形成当前产品配置与审批对象；BudgetRevision active 必须先补**精确预算审批链**，包括待批准金额/有效期/Owner/预算对象内容哈希、冻结 ImpactPreview、由现有权限系统判定 maker/checker、ApprovalEvent 的当前性/撤销/过期、同事务 CAS/幂等 Budget Receipt；负例必须覆盖错租户、旧 revision、旧预览、同人审批、重放与已批准后内容变化。不能直接解除 422 或调用 Store 发布 active。之后独立实现当前三身份和 Host identity/assignment 正式供给、配置绑定与当前安装运行批准；前述权威齐备才有界启 Host，再看自然首链。缺合法用户决策的具体当前对象保持禁入，独立代码研发继续。

E17-x 最小代码入口预定 `services/aos-api/aos_api/routers/aip_budgets.py`、`aip_budget_store.py`、预算合同及现有 Action/ImpactPreview Store 的精确读取接口，测试先扩 `tests/aip/test_aip_budget_api.py` 与预算 PG 联合测试；开码前细化批准对象和表/事务边界，不能自造假审批或改当前真实库。浏览器 `browser-pilot` 暂不可用，本波无新截图；未启 Host/worker/Provider，未碰 dev-org、旧 12 Run、手工 Run、230 L0。
