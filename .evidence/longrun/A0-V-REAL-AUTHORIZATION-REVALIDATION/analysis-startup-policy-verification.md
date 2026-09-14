# SC1 启动政策蓝图验证

基线e3951342，子Lease A0V-ANALYSIS-STARTUP-POLICY-20260914，m1串行。方案analysis-startup-context-design.md SC1已先补全格式。

包蓝图升v2，新增必填startupContextPolicy。Host仅接受固定analysis-start用途、单一原事件/Case/Run关联事实、业务事实not-evaluated、由L1取待取证清单、portrait首阶段的skill-publication-contract用途。完整规范对象校验，拒绝未知批准字段；不改变阶段模板正文或Skill选择。

Red 10 failed/17 passed（旧蓝图缺政策）。Green 44 passed/7 warnings/3.70s：蓝图、Port、当前选择、真实隔离PG模板准备、原START命令。九种重新计算hash的政策替换仍拒绝。首次回归路径误写导致未收集，修正后以上结果为实际执行。AR2 ar2-7 1895/173/93，各错误数组为空；diff --check通过。

旧签名候选不改，主安装未升级，新Host会拒绝旧v1蓝图；这是显式协议升级，不可宣称旧候选具备新功能。未调用模型/主库写/外发/push，230 L0挂起。测试不证明真实事件证据/评估有效性。下一波SC2当前事件启动证据；SC3当前Eval/Context和SC4Saga/TaskRun仍待完成。
