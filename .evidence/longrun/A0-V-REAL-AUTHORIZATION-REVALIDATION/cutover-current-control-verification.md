# 切换产品控制层验证

基线3577c7d5。三项新增先失败（缺失模块）；实现后完整恢复、回滚、当前撤权、旧键重放、无效请求与启动装配联合31 passed。中间测试参数request与pytest保留名冲突，改测试参数后通过，无产品逻辑妥协。AR2扫描1827，五类错误空；diff检查通过。

PG证据：当前权限校验与prepare exact审批在同pid/tx；第一次成功和授权下原键重放返回同Receipt；撤权后原键重放拒绝，Receipt数量保持1；首次无权调用无切换记录。完整prepare/pause/commit/validate/resume及rollback-prepare/rollback-commit每阶段均进入当前权限门。原Store测试路径不改。

产品控制层未开放HTTP、未重载API，真实9项登记仍禁入。下一波按明确阶段类型接写HTTP，prepare须真实注册Receipt引用；原key回读保留，未知提交不重试。随后当前授权操作员的精确Proposal/Approval和真实切换；不得用测试seed。
