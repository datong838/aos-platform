# b76 锁入口第一段

真实runtime FOR UPDATE前测1failed7warnings14.71s，permission denied for exact epoch table；原失败runtime-lock-red保留，不xfail。最小SECURITY DEFINER/fixed search_path锁函数候选1passed7warnings15.79s，runtime只有EXECUTE且原直接UPDATE仍42501；合法head锁后admin状态0/0/0，wronghash及canary拒绝，状态仍0/0/0；b75原Store/rawSQL/缺head/canary/事务rollback继续同波执行。编译与diffcheck通过。

重要未完成：函数尚未进入Store pre-replay连接工厂；没有组合并发proof；trigger仍随机fixture WHEN前缀；本段只解决调用方无UPDATE时取锁入口的可行性，不称完整b76合同完成。runtime EXECUTE测试权非正式signed身份，admin fixture初始化非正式source。生产Store/migration/current135库不动，八来源/Owner/install epoch/first chain仍pending。无UI变动浏览器不适用。

下一b77延续原完整合同：去WHEN前缀，源head触发器全表在一次性库生效；调用前取exact锁再Store _replay，epoch仅event触发器推进，两个精确PID共同锁等待、同key两返回一event/Receipt/epoch、冲突/新key既有event/首次回滚、撤销先旧快照和评测先等待全部验证。先补文件级方案/Task/Lease，不动生产库。Goal active。

B76关闭的b75相邻本次1passed7warnings，原触发器ACL/Store/rawSQL/rollback断言保持；未做本波库前后计数，不声称新库残留全量证明。
