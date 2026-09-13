# UI 当前成员身份事务读取

基线 90620186。新增 services/aos-api/aos_api/extension_runtime/ui_current_principal.py 和 tests/extension_runtime/test_ui_current_principal.py。为后续 UI 调用门禁提供同一事务内当前主体事实，不能信任浏览器缓存的角色，也不创建成员或授权。

输入必须是服务端 TenantScope、已验证 subject、当前签名元数据要求的 marking 集合。检查连接已在事务且 GUC scope 一致；meta_membership 精确单行 FOR SHARE，逐个要求的 authz_tuple bearer marking FOR SHARE，缺少即拒绝。返回不可变 subject/scope/role/已核 markings，不带 executable/approved。与现有 CurrentControlPermission 相同，配置远程 OpenFGA 时拒绝本地权威替代，后续由明确适配器处理。

本波只交付事实读取，不给任何角色附加写权限，不将旧 permission.actionTypes=[] 变为允许。真实 UI 写入还须当前签名操作声明、角色策略、业务审批与精确目标均在执行事务闭合。测试涵盖事务缺失、跨租户、成员撤销/重复、标记撤销、主体格式与远端模式，SQL 不含写入及提交。
