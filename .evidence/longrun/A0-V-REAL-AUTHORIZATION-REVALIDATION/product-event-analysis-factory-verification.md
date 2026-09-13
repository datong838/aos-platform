# 分析工厂与原批次定位验证

基线59f1fb17。build_event_analysis复用单一source consumer及原completed journal，另造同scope/install/gen/markings growth invoker。discover_claim_origin先查不可变origin，再在现有当前候选SQL中限制policy/run/actor。分析准备/提交入口再次匹配original run/actor，origin进入快照。

Red工厂缺方法；Green23项factory/discovery/analysis准备与编排，补充locator1项通过。专用18432 SQL证明精确run-2即使limit1也可定位，不做前100条内存搜索；错误run/actor当前准备拒绝。locator的origin读为具名double，真实origin RLS/hash见上一波。Source/installed仍具名double，非真实Run完成证据。

AR2-7 1887/169/93无错误，diff --check通过。无主库迁移/Host重启/push。下一波worker按live target精确领取→origin定位→factory→analysis→Receipt，并用真实PG验证异步默认时钟、禁入、未知结果行为。
