---
name: qyh-ops-router
description: Route requests about 栖月汇、栖月汇微商城、yanpanji 管理后台、微信小程序前台、体验码、店主分润、客户绑定、Niushop 数据或全店经营体检 to the correct wchat-qyh-ops skill. Use when the user asks what exists, where to look, how to revisit a page, or wants a broad Qiyuehui investigation without naming a specific workflow.
---

# 栖月汇运营研究路由

先读 [能力与任务地图](references/capability-map.md)，根据用户问题选择最小技能组合。首次平台/店铺摸底或全店体检还要读 [双域全息内省](references/dual-plane-introspection.md)。

## 铁律

> 先确定经营问题和证据面，再打开页面；不以重新遍历全部菜单代替思考。

## 路由

| 用户意图 | 使用技能 |
|---|---|
| 后台菜单、页面、配置、订单/商品/会员定位 | `qyh-admin-observation` |
| 微信小程序首页、商品、内容、购物车、会员、我的店铺 | `qyh-miniapp-observation` |
| AOS 数据集、对象、指标、Ontology、数据缺口或源字段补证需求 | `qyh-data-semantics` |
| 已批准 DataNeed 的源库发现、Mapping、Dataset 和本体水合（仅 Data OS/FDE 身份） | `qyh-data-onboarding` |
| 体验码、消费即店主、客户绑定、优惠券赠送、分润 | `qyh-social-distribution` |
| 首次全店分析、周复盘、专题探究、问题机会、方案与八工作台承接 | `qyh-business-diagnosis` |
| 截图、证据卡、脱敏、冲突、停止条件 | `qyh-evidence-capture` |

## 默认工作流

1. 明确目标店铺、经营问题、时间窗和允许观察范围。
2. 判断需要后台、消费者端、AOS 数据集/本体投影，还是多面核验；源字段不足时形成 DataNeed，不跨层访问源库。
3. 读取相应技能的页面地图/对象地图，不重新从首页盲找。
4. 先建立事实与未知，再按业务形态调用经营探究；不得从菜单清单直接跳到方案。
5. 用证据技能记录 source、collectedAt、scope、quality、confidence 和 nonClaims。
6. DataNeed 只能 Handoff 给具备 Data OS/FDE capability binding 的 `qyh-data-onboarding`；Workshop 不得调用其源库工具。
7. 遇到写操作、认证挑战、PII 扩大或店铺身份不清立即停止。

## 输出契约

输出必须区分：`OBSERVED_UI`、`SCHEMA_EVIDENCE`、`OWNER_EXPLANATION`、`BUSINESS_HYPOTHESIS`、`SOLUTION_CANDIDATE` 和 `UNKNOWN`。
