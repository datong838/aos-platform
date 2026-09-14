# SC4-5e9a 支付来源范围与条件字段

2026-09-14，基线6ea74b88；Lease A0-V-SC4-CONDITIONAL-SOURCE-FIELDS。

源政策可选conditional_only有界唯一标识符→固定非空字符串。选中判别列必须精确同名同类型同值过滤，直接PII/quasi/sensitive/global/映射排除优先、不可覆盖。MappingReadSpec仍原结构，原参数化过滤与逐行校验复用，无SQL语法扩展或源权限扩展。

红测7 failed/25 passed，实现后82 passed/7既有警告/4.67s；含原存储/Owner/扩展候选与真实纯物化跨事件反例（合成输入）。AR2 1909/187/93五数组空；diff-check通过。未主安装或主业务写入。

源代码依据：niushop/app/model/system/Pay.php addPay及状态常量；OrderCreate/OrderPay/OrderCommon传普通订单事件和order_id，SuperCardOrderService传会员卡事件和会员卡订单ID。重新支付关闭原支付、替换订单交易号。真实只读聚合：203普通+8会员卡；普通状态-2有94条（当前交易号匹配72）、状态1有1条、状态2有108条，父订单缺失及会员不符均0。仅证明此次聚合和本地代码相符，不声称源部署代码版本已鉴证或正式关系Receipt已完成。

SC4-5e9a：源判别列conditional_only精确范围约束完成，82项回归通过，其他业务事件行物化拒绝。真实支付拆分203普通订单+8会员卡；普通94关闭中22旧交易号不同，父订单/会员无错配。下一普通订单Payment快照候选，仍不声称关系Receipt或主首链完成。
