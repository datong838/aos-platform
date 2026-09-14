# SC4-3c1 固定暂停初始化合同

基线f7327f8d。完整授权/预览/运行方案analysis-bootstrap-runtime-design.md已补原SC4清单。新增AnalysisBootstrapIntent，绑定原Occurrence、EventPolicyControlReceipt、租户、完整CompilationBinding和Receipt，固定ecommerce_analysis_bootstrap/paused-before-first-step，业务与外部执行标志必须严格False。核对Run/Task/Profile/Logic/SkillSet/职责及编译请求hash，checked重新解析嵌套可变数据。仅合同，不注册Action、不放宽风险、不授予权限。

RED：14项缺模块失败。正向fixture补齐领域exact引用规范中的receiptId=null后，累计合同/组装/真实编译PG 33 passed（5.49s）。拒绝run-now、业务/外部授权扩大、0冒充False、跨租户、错误源引用类型、Task/Profile/请求hash错接、嵌套hash及未知skipApproval字段。实际来源/Receipt仍须后续当前Owner及原Store验证，不能靠此hash获得权限。

AR2 ar2-7 1900/178/93，全部错误为空；git diff --check通过。下一SC4-3c2本任务启动Preview，然后专用Action当前守卫和实际TaskRun原子组合；完整事件START、主安装及业务首链尚未完成。不push，230 L0挂起。
