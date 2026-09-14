# SC4-5e9b 普通订单支付候选

2026-09-14，基线777cdae8；Lease A0-V-SC4-PAYMENT-SNAPSHOT-CANDIDATE。

1.12.0树7d0eaeb6c99da59f8e9f08f78607da60320f97bdaab881184c4f7e6a47fd9587不变；新版本只改bundle/p12/masking/evals四处。P12精确site_id=1 AND event=OrderPayNotify；event从无条件禁止改为conditional_only固定值，其余敏感保护不变。会员卡支付不进入普通订单范围。

去掉重复pay_type选列，选择12个必要字段；relate_id→orderId在普通事件命名范围内，仍需真实父订单关系验证。源码五类支付状态保留、显式删除，未付时间0保持未知，精确金额非负。公开投影不含event、内部id/site/delete。无pay_duration_min或其他派生伪造。

先缺生成器3红测；实现后75 passed/7既有警告/5.89s；十二类合成规范对象整包评估通过，realFulfillment=false。AR2 1909/187/93五数组空；memory validate与diff-check通过。未主部署、真实采集、发布安装或主业务写入。

SC4-5e9b：普通订单支付1.13.0候选完成，75项回归通过，十二类静态规范对象通过。树07478676ef5be20e10d185fe98113932a16a0b41d973248729285eaf4879015b；仅203普通订单支付范围，排除8会员卡，历史关闭重试保留。静态12/12≠主采集12/12；主库仍先前2/12，实际关系/完整补齐/首链/八场景未完成。下一复用受控快照入口落实完整批次与跨对象关系，再Outbox/Fulfillment/恢复。
