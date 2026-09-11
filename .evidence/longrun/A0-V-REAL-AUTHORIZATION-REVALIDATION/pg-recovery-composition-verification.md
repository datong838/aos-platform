# PostgreSQL恢复事务组合验证

2026-09-11，基线ddd96732，A0V-PG-RECOVERY-COMPOSITION-20260911。

既有跨连接恢复组合参数化SQLite/PostgreSQL Store。PG分支使用隔离schema、真实six-table Store、scope runtime/RLS/local sequence；与原Journal、派生Journal、Dataset回执和claim事务组合。

验证5场景通过，新增PG分支覆盖基础已提交后保存派生失败再恢复、派生准备先提交再执行、基础/派生exact重放、Dataset回执失败回滚/内存发布失败恢复、空观察无Store调用、原failed claim禁入回滚/并发一个成功。diff-check通过。本波仅测试修改，未动产品。

限制：Store表由metadata创建，meta_run等为最小fixture；projected仍显式设置，源为fixture。不是完整production migration或实际projector/真实首链验收。public未迁移、API未重载。下一波实际投影器组合及迁移安装兼容性，然后产品恢复入口。八工作台仍未完成，不push，230 L0挂起。
