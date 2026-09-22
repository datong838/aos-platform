---
name: douyin-store-evidence-capture
description: Capture privacy-safe, auditable evidence from Douyin Store pages and authorized data products, including time window, denominator, source state, conflicts, and nonClaims. Use for 抖店截图取证、指标证据卡、经营结论复核、冲突登记或分析交接.
---

# 抖店证据记录

按 [证据卡模板](references/evidence-card.md) 记录。只保留经营判断必要信息，不记录客户姓名、电话、地址、订单号、账号标识或凭据。

## 证据层级

- `VISIBLE_FACT`：页面当前可见且口径明确。
- `PARTIAL_VISIBLE_FACT`：页面可见，但分页、时间窗、分母或加载不完整。
- `PLATFORM_CAPABILITY`：平台提供功能入口，不代表店铺启用或有效。
- `INDUSTRY_BENCHMARK`：行业词、同行比例、平台预估，不是店铺事实。
- `OWNER_CONTEXT`：经营者提供的背景，需要和数据分开。
- `HISTORICAL_DESIGN`：历史接入方案，只说明方法或目标。
- `INFERENCE`：由多条证据推断，必须有竞争解释。
- `UNKNOWN` / `PERMISSION_BLOCKED`：缺数据、缺权限或加载失败。

指标卡必须有实体、页面、采集时间、业务时间窗、分母、加载/权限状态和 EvidenceRef。跨页面数值冲突不得平均或择优；分别保留并生成对账任务。
