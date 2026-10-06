# 恢复库有效角色权限核验
Rules：231/AOS工程交付、原restore Task，候选有效继承权限核验及publication签名方案，选前者。
固定隔离恢复库只读pg_roles/memberships/有效DB-schema权限和public表has_table_privilege/has_column_privilege/PUBLIC SECURITY DEFINER入口。新增五角色必须NOLOGIN/NOINHERIT无高权/无membership，schema CREATE及DB CREATE/CONNECT否；TEMP来自原PUBLIC单独记录，不按NOLOGIN冒充无权限。evaluator实际表/列权限与a144定义完全一致，issuer与a150完全一致；中立owner表所有权/函数表面已独立证据，不重做业务验收。检查仅public已声明schema范围，不宣称集群全域最小权限。
证据文件本目录effective-role-plan.md/effective-role-verification.json，私有完整结果aos-recovery/current150-.../effective-role-20261006-0815.json；无业务代码或库写入。未知PUBLIC SECURITY INVOKER入口仅记录并留后续，不自动撤销。
