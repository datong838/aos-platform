---
name: douyin-store-platform-observation
description: Inspect a logged-in Douyin Store merchant backend in read-only mode, directly locate menus and pages, scroll normal pages to the end, and capture platform capabilities and store-visible facts. Use for 抖店平台摸底、菜单盘点、页面定位、店铺只读观察、精选联盟或电商罗盘复查.
---

# 抖店后台只读观察

先读 [导航地图](references/navigation-map.md) 与 [观察规程](references/observation-playbook.md)。研究美国裕威参行时，再读 [2026-08-22 观察快照](references/2026-08-22-us-yuwei-store-observation.md)。

## 观察顺序

1. 首页、店铺与体验：确认实体、行业、经营状态、体验分和违规/权限边界。
2. 商品、订单与售后：确认价格带、库存、销量、内容完整度、订单体量和退款/售后结构。
3. 搜索、短视频、直播、商城：确认自然流量供给、内容供给、货架机会与真实效果。
4. 精选联盟、用户、会员：确认达人供给、佣金计划、获客来源、留存与复购机制。
5. 电商罗盘：交叉核对交易、内容、搜索、达人、人群和市场口径。

每个正常页面等待业务区加载，再从顶部滚动到底。明确无权限时记录 `PERMISSION_BLOCKED` 并跳过。禁止点击任何创建、编辑、保存、导出、上下架、投放、触达、退款、打款、开通或关闭按钮。

## 每页最小记录

中文菜单、稳定路径、页面标题、时间窗、当前实体、筛选/Tab、指标及分母、加载完整性、权限、平台能力、店铺事实、行业基准、可执行按钮类别、冲突与 nonClaims。
