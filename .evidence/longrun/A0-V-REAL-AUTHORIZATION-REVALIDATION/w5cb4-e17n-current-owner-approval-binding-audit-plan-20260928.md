# W5CB4 E17-n｜当前安装 Owner、审批及配置绑定只读审计方案

## 依据

复习 231-3 安装/运行从属状态机及 E17-l/m。需要消除一个准入语义混淆：代码中的 `LiveInstallationLifecycleOwner` 是由 Host 在发现 pending runtime-apply outbox 或有效 rehydrate binding 后构造的进程内执行 Owner，不是启动前可提交的人工审批凭据；`bundle_installation.created_by` 只是创建者，批准人要看不可变 decision。不能把 Owner 名词直接写成一个虚构的启动前字符串门。

## 只读文件级检查

1. 读取 `ar1_001`/`ar1_002`、安装 decision schema、`pending_preparation_directory.py`、`production_preparation.py`、当前权限/配置合同，列清操作审批与执行 Owner 的不同来源。
2. 以当前权威卷、`a0v_109` 库只读查询精确 `org-org/dev-project` 安装 current/active revision、创建者/不可变 decision；runtime operation/binding/configuration/Host assignment 与 Action proposal/approval/receipt 的当前数量，不查商城源或敏感负载。
3. 只记录现状与下一步可编码的准入合同，不写库、不启 Host、不把零行推论成历史已清退。发现 E17-m 的“正式生命周期 Owner 前置”表述与实际构造顺序冲突时，明确修正下波设计，而不削弱当前硬禁入。
