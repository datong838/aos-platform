# b75 数据库事件驱动epoch隔离候选（待实施）

b74原Store实际(0,1,1)RED是前测。不改生产Store/migration，只在disposable创建随机trigger/function/NOLOGIN NOINHERIT NOBYPASSRLS owner；固定search_path pg_catalog,public，函数所有表schema限定、PUBLIC执行拒绝。作用限定本fixture sources，不以未覆盖其他source的trigger当全局门。

临时exact epoch表ENABLE/FORCE RLS。runtime保留SELECT，撤销任意UPDATE(epoch)授权；trigger owner只SELECT source/head、UPDATE(epoch)，租户策略基于同一transaction GUC，不能BYPASSRLS。仅source frozen exact hash匹配且head存在才能插撤销事件；BEFORE INSERT同事务推进一次epoch，缺source/head/tenant不匹配拒绝。初始化仍admin fixture，不等正式issuer。函数/trigger创建不是给runtime发正式身份。

验证原真实Store不包UPDATE应event1/Receipt1/epoch1；直接runtime UPDATE head42501；raw SQL插新fixture event同样推进head，不能绕过；missing exact/hash/foreign tenant返回拒绝且零event/Receipt/head变动；提交前异常证明原event/head/Receipt全部回滚；同已撤销source不同key不再推进epoch。每案例独立freshsource，不能用删除事件复用状态。序列化replay前行锁与多来源evaluator并发继续b73合同，但正式受限lock入口另项，不宣称事件trigger代替先锁。finally先drop trigger/functions/role，恢复仅临时表测试授权后继续原b71/b72回归，整个库conftest清理。

实施前补Task/Lease及精确代码方案，检查原helper definer已有RLS政策/权限和PG触发器调用语义；RED保持不改期望。全两个顺序、b73/default相邻、库前后与ACL回读、source/方案自复审。当前135库只读，真实迁移和正式issuance完整门未放开。禁止为GREEN直接运行正式迁移或宽授权runtime。
