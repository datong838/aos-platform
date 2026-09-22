---
name: wx-store-controlled-operation
description: Safely perform one explicitly authorized WeChat Store change after resolving an exact target, previewing the intended mutation, and planning readback. Use only when the user clearly authorizes a specific save, publish, stock, price, listing, coupon, promotion, refund, or configuration action.
---

# 微信小店受控操作

默认禁止写。只有用户明确说出“哪家店、哪个对象、什么动作、目标值”后才进入本技能。

## 五道门

1. **实体门**：确认渠道和店铺名称。
2. **对象门**：用唯一 ID、完整商品名或订单号解析单一目标；列表勾选框保持未选。
3. **影响门**：说明会修改的字段、可见范围、是否立即生效和回滚方式。
4. **确认门**：保存/发布/上下架/退款/打款等最后一步前再次展示摘要。
5. **回读门**：提交后重新打开同一对象，读取状态、时间和目标字段；unknown 不报成功。

批量操作、删除、资金、退款、关闭服务、联盟自动推广、全店价格/库存变更必须单独授权。验证码、风控、权限变化或目标不唯一立即停止。
