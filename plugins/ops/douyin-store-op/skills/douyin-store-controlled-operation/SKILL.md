---
name: douyin-store-controlled-operation
description: Perform one explicitly authorized, reversible Douyin Store operation after exact target, current state, impact, and rollback are verified. Use only when the user explicitly asks to execute a concrete 抖店 action such as editing one product, changing one plan, or publishing one approved item; never infer authorization from analysis work.
---

# 抖店单目标受控操作

分析、浏览或“可以看看”不构成执行授权。执行前必须重新确认：店铺、对象 ID/名称、唯一动作、目标状态、影响范围、可逆性、审批人和回滚方式。

## 执行门

1. 先只读定位并回读当前状态，排除批量选择和相似名称。
2. 展示拟变更摘要；高影响动作需要用户再次确认。
3. 只操作一个目标，不使用批量按钮，不顺手处理其他问题。
4. 提交后重新打开详情或列表确认服务端状态；保存前后证据。
5. 状态不明、页面漂移、二次验证、权限异常或结果 unknown 时立即停止，不重试副作用。

禁止删除店铺/商品、提现、退款、打款、批量上下架、批量改价、批量触达或未经批准的投放。凭据、客户隐私和结算信息不得写入日志或 Skill。
