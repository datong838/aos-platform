# b75 事件驱动epoch候选验证

b74原RED(0,1,1)保留9af12359 evidence。b75新opt-in必须配b74合法链，独立NOLOGIN/NOINHERIT/NOSUPERUSER/NOBYPASSRLS owner；FORCE RLS临时表，runtime UPDATE(epoch)撤销，owner仅SELECT source/head与UPDATE(epoch)，两表tenant policy；函数SECURITY DEFINER/fixed pg_catalog,public/所有关系schema限定/非runtime可EXECUTE。

实际首候选1passed7warnings15.66s；补ACL/函数/RLS独立回读及事务内Receipt/epoch断言后，revoke-first/evaluate-first/b73/default各1passed7warnings。节点24.51/24.69/24.27/24.22s；summary与原输出保存。runtime直接UPDATE42501；原Store不包epoch更新仍(1,1,1)，samekey重放不变，newkey既有event(1,1,2)不多推进epoch；rawSQL新来源(1,1,0)，证明事件写路会同步head但不伪造Store Receipt。缺head(None,0,0)、错hash和dev-org canary(0,0,0)均42501。全新Store提交前代理确认事务内event1/Receipt1/epoch1，异常后独立admin(0,0,0)。不删除event复用fixture。

finally先drop trigger/function/policy/owner，恢复临时runtime列权限，再执行原b70/b71/b72检查；相邻b73独立复验并发幂等/首次失败/冲突。回归批次库49→49，首候选运行前未单独计数，不扩大逐节点证明。编译与diff通过；首次编译因SQL字符串引号SyntaxError，修复后才运行PG，未作为业务RED。误建空目录已仅rmdir空目录，无其他数据操作。

仅两个测试文件；默认关闭无行为变动；源初始化为admin fixture，不是signed issuance；WHEN随机bundle前缀不是全表正式门。取消runtime UPDATE后普通FOR UPDATE不能直接使用，trigger发生在_replay后不能替代锁入口。正式完整组合b76详next-contract.md；源/Owner/install epoch、八依赖、W-L20与135迁移另门。未改生产Store/migration/current DB/Host/worker/Provider。无UI改变，浏览器不适用。

方案一致性：完成本wave候选的真实Store/rawSQL/ACL/缺exact/canary/rollback，各结论与断言对应；不称全局DB或正式运行合同完成。Goal active，authority AOS-001329及强投影本次CURRENT，继续已登记安全波。
