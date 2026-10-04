# b82 验证与复审

RED：新表未实现，1failed/11errors、7warnings、4.75s；UndefinedTable真实一次性PG，不是HTTP RED。最小迁移首次专项18passed/6failed、4.98s：6项预期错误，旧guard确为SQLSTATE55000/AIP6_REGISTRY_APPEND_ONLY；修正test，未修改生产guard。

最终29passed/7warnings、4.83s：新增schema17项、b81连接9项、b45事务接缝2项、普通Evidence撤销1项。新表默认零行，普通非空license_summary不自动mint；runtime同tenant只读，canary/空tenant不可见、所有写/TRIGGER/REFERENCES权限无；PUBLIC无ACL、三表FORCE RLS。错source revision/hash、错tenant、错installation/Receipt FK拒绝，head错source/tenant和负epoch拒绝。issuance/proof UPDATE/DELETE/TRUNCATE连maintenance常规SQL也拒55000。缺八维键/无效期限拒绝；JSON/哈希只结构，不把管理员test-only refs当真实授权。

签名full-schema实际RED14.51s：两处硬编码135，实际reader正确回136。追加compat Task后复用已有Alembic ScriptDirectory唯一head作为独立预期，生产reader/恢复135探针不改；最终1passed/7warnings、15.14s。安装到Owner证据仅test-only既有路径，EVIDENCE_ONLY_NO_START/PREFLIGHT_ONLY_NO_RUNTIME_START限制继续，不授自然首链。

py_compile三个文件与git diff --check退出0。after读回历史测试库49、b81_evaluator随机roles0；没有前置计数，不报告库数量before/after一致。测试fixture会删除自身一次性库；不删历史库。当前135命名卷/服务没有迁移、重启、业务操作。既有9项用户M/历史untracked保护；无页面代码，浏览器不适用。

一致性复审：符合b80/本波plan：独立proof不覆旧hash；generic Evidence未改；精确source hash FK唯一索引（冗余于原PK、不回写源）；installation/Receipt只历史来源引用，不能代替当前签名、Owner/policy/预算授权；无正式login provision/表写授予。downgrade拒静默删历史。当前迁移仍候选，真实135升级必须独立备份恢复/零执行窗口门。proof JSON八键不能验证八维语义、hash不能仅格式当canonical，receipt引用不证明正确operation，sourcehead维护owner可改；下一受限正式命令必须处理这些业务门。

下一b83登记：生产可信License来源读/共同head锁与数据库事件驱动撤销，原Store pre-replay锁仅可信source域，generic普通证据保持原合同；随后可信初始化和正式evaluator同事务全八源命令。必须读真实Owner/policy authority，不虚构字段或以created_by赋权；缺许可fail-closed而继续安全开发。八维逐源双顺序、正式发行正向、幂等/rollback/旧快照以及实际经营链仍未证明。整体Goal active。
