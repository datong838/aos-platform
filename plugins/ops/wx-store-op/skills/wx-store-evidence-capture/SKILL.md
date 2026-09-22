---
name: wx-store-evidence-capture
description: Record privacy-safe evidence cards for WeChat Store observations, including source page, channel, store entity, time window, collected time, status, quality, conflicts, non-claims, and next evidence need.
---

# 微信小店证据卡

每条记录使用：

```text
channel: 微信小店
entity: 具体店铺
page: 中文页面 + 稳定路径
collectedAt: Asia/Shanghai 时间
metricWindow: 页面时间窗
evidenceType: PLATFORM_CAPABILITY | OBSERVED_STORE_FACT | PERMISSION_BLOCKED | OWNER_EXPLANATION
fact: 脱敏事实
quality: COMPLETE | PARTIAL | LOADING_UNCERTAIN | CONFLICTED
nonClaims: 不可推导事项
nextEvidence: 下一条补证需求
```

不得写入联系人、手机号、地址、订单号、账号 ID、认证信息、资金明细或客户身份。截图进入共享证据前必须脱敏。
