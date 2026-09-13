# 原批次精确事件回读验证

基线bfbadae0。run_candidates不变，run_event只读原proof中的唯一指定事件，维持SourceOwner/parent/derived/projection evidence和实际payload hash校验，回调不得延迟。已消费排除条件仅在明确exact-key时省略。

Red3失败（缺参数/方法），Green25项reader及consumer回归。真实18432临时表证明已有Occurrence事件不再列作候选但可精确回读、不在proof则拒绝、实际payload篡改拒绝；Owner编排替身覆盖空批次/重复/错key/deferred拒绝。非真实来源权限验收。AR2-7 1885/169/93，无错误；diff --check通过。

未部署、无主库写入。下一波正式分析承接服务：prepare释放事务→installed命令→相同当前claim/source/policy上下文复核→AnalysisAdvanceHostService写Run/Receipt。最后由异步dispatcher接收Receipt，未知结果仅对账。
