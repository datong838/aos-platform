# UI 当前调用约束验证

基线 ef87d07e。严格 RuntimeUiInvocationTarget 与当前 RuntimeView 比较，精确 read/command 声明检查；Canonical Router 可选 ExpectedRuntimeTarget 与新签发 DispatchRef 比对，不允许 UI 目标进入 legacy 分支。旧不传目标的调用契约保持。

50 项门禁/Canonical Router/HostPort 测试通过，7 项既有依赖警告。包含拒绝时执行器调用 0、提交 0；签发后 epoch 变化由原事务门禁拒绝。ar2-7 闭包扫描 1835/分类161/迁移93，五类错误为空。diff --check 通过。

合同为前置约束，不是运行授权，尚未接 HTTP。待闭合：当前签名模块角色/marking 与 caller subject 的业务操作权限，检查到事务期间的权限/签名变化，真实包内 read 端口。当前 HostService 多数以固定 executor_identity 留痕，不能据此推断任意 UI 用户可调用。下一波梳理并设计当前主体的事务内调用策略；在其完成前不开放 UI 业务转发。无真实 Run、路由切换或对外副作用。
