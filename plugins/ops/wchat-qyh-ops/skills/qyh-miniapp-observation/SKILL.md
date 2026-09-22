---
name: qyh-miniapp-observation
description: Observe the logged-in 栖月汇 WeChat mini-program consumer experience in read-only mode. Use for home, category, product, content, cart, member center, personal store, share, gift coupon, experience-code, customer, and earnings journeys, or when validating how an admin configuration appears to consumers.
---

# 栖月汇微信小程序观察

先读 [消费者端地图](references/miniapp-journey-map.md)。

## 核心原则

> 小程序不是后台装修预览，而是真实消费者旅程；必须从用户任务理解，而不是只截图页面。

## 观察旅程

发现 → 内容理解 → 商品决策 → 购物车/成交 → 会员关系 → 分享传播 → 个人店铺与收益。

## 三面核验

小程序入口只能证明消费者可见性。任何机制还需与后台配置和数据对象交叉验证。分享按钮不证明分享发生，收益页不证明单位经济可持续，个人账户结果不代表平台整体表现。

## 边界

禁止下单、支付、赠券、发送体验码、修改资料或实际分享，除非用户另行授权并通过独立 Action 门。出现个人资料、地址、电话、客户或收益明细时只记录结构，不转录值。
