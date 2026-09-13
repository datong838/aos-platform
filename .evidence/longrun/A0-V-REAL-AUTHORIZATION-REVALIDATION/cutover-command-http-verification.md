# 分阶段切换写接口验证

基线4eaf0bab。请求合同先8 failed，新增接口与当前控制PG联合57 passed；补精确审批条件不满足的安全409映射后接口专项33 passed。测试夹具重复建已有表/字段导致两次夹具失败，最终复用原安装记录更新测试etag，无产品schema修改。AR2扫描1828五类错误空，diff检查通过。

七阶段输入类型及新/原键返回201/200、Principal身份及双租户、安装path和etag传递、首次origin必填、resume验证Ref必填、key/If-Match缺失或重复拒绝、body actor注入拒绝。真实隔离PG证明错安装409和错etag412均无阶段记录；当前权限和Store审批事务不拆分。审批条件阻断409，存储不可用503，不透传内部异常。

代码未实际调用主库写接口，9项正式登记仍禁入，未伪造审批。API运行仍c3e57bf9；新控制接口待受控重载。下一波读取主库真实ActionType/Proposal/Approval Owner能力，形成当前注册的具体切换审批材料，经既有Owner落库；没有真实凭据/角色时不伪造身份。前端N7/N8交付仍按runtime-workshop-entry-gap-plan继续。
