# 新增ACL审计
Rules：231/AOS工程交付、原restore Task。候选新增权限原迁移比对及publication方案；选择首项。只读已冻结八步catalog delta，逐步grantee白名单、无PUBLIC/可转授权/默认ACL新增；a144 evaluator精确SCOPED_READ+GLOBAL_READ+三Action SELECT、两表INSERT、LOCK_COLUMNS+BINDING_UPDATE_COLUMNS UPDATE；a150精确15表SELECT/5列UPDATE；145/147 runtime精确新表SELECT/INSERT。owner自身表/索引所有权ACL不冒充额外运行授权。原恢复Task未收口，无源改变。
新增证据文件仅本目录added-acl-plan.md、added-acl-verification.json；无需业务代码修改。此证明显式ACL增量，不证明全部有效继承权限、RLS实际运行或完整业务COMMIT。
