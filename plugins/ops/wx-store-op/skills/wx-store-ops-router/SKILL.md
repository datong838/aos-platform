---
name: wx-store-ops-router
description: Route requests about 微信小店、微信小店后台、店铺菜单、商品订单、推荐搜索、会员复购、优选联盟、经营数据或微信小店经营分析 to the correct wx-store-op skill. Use when the user asks what exists, where to look, how to revisit a page, compare stores, or conduct a broad WeChat Store investigation.
---

# 微信小店运营研究路由

## 铁律

先明确渠道、经营实体、问题和证据面，再打开页面；不要用重新遍历全部菜单替代思考。

| 意图 | 技能 |
|---|---|
| 菜单、页面、功能、直达路径、只读巡检 | `wx-store-platform-observation` |
| 新店冷启动、全店画像、周复盘、专题探究、问题机会、方案候选、跨店比较 | `wx-store-business-diagnosis` |
| 用户已明确批准保存、上架、下架、发券等单一动作 | `wx-store-controlled-operation` |

## 默认流程

1. 冻结渠道为“微信小店”，再确认具体经营实体。
2. 明确时间窗、分析问题、可见权限和只读/写授权。
3. 从导航地图直达目标页面，等待加载完成并滚动到底。
4. 区分 `PLATFORM_CAPABILITY`、`OBSERVED_STORE_FACT`、`BUSINESS_HYPOTHESIS`、`UNKNOWN`。
5. 数字记录页面口径、时间范围、采集时间和权限；冲突不强行合并；不得从页面地图直接跳到经营方案。
6. 写操作必须切换到受控操作技能，重新核对目标和授权。

## 输出边界

- 不记录认证材料或个人敏感信息。
- 明确“暂无权限”即停止该页，不把它当业务空值。
- “加载中、空白、遮罩、暂无数据”先判断页面状态和权限。
- 不把平台推荐的提升幅度、同行案例或规则示例当目标店铺实际效果。
