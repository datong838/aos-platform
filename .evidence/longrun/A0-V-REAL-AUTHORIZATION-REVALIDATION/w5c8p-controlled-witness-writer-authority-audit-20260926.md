# W5c8p｜受控见证写入权限审计

## 结论

当前 `a0v_097` 只保护 sidecar 的运行角色权限、RLS、文本自哈希和原 claim 身份；manifest hash 未与原 input 建数据库级复合 FK。表所有者可首次 INSERT，自哈希正确并不代表原 input 等值，不能把 owner 直插当受控回填，也不能向 runtime、directory 或 maintainer 放开 INSERT/EXECUTE。

## 后继函数最小合同

1. 独立 `NOLOGIN NOSUPERUSER NOBYPASSRLS NOINHERIT NOCREATEDB NOCREATEROLE NOREPLICATION` 角色；迁移需校验同名现存角色属性及成员关系，不得自动把它授予 runtime/maintainer 或应用登录角色。函数 owner 与该角色精确绑定、固定 `search_path`；默认所有应用身份无 EXECUTE，另立受控运行身份/Host-fence 门。
2. 函数需在单事务内精确双租户读原 `a0v_045` claim/input/member，验证原 claim request hash、原 input manifest hash、两份传入 canonical 文本的 UTF8 sha256、解析后 JSONB 与原保存 JSONB 等值、member 数/ordinal/runId、actor/tenant。缺任一原行或 hash/文本数值漂移即拒绝，不做猜测回填。
3. 原表不可变，sidecar 只能 INSERT；同键不同文本拒绝。并发同键只允许一个不可变结果，未知提交边界仍按上位规则冻结，不因函数可幂等而自动重试。函数不能返回 ACK、Receipt、Run 状态或执行授权。
4. 完整隔离 PG 先证明：runtime/directory/maintainer/PUBLIC 均无 INSERT/EXECUTE，专用角色无登录/BYPASSRLS/成员外溢，成功原组、缺 input、跨租户、hash/JSONB 漂移、成员不符、重复与并发。成功测试只是 disposable DB 的结构/语义证明。

## 本波退出

仅新增审计与计划修订；无 migration/运行 writer/真实库变化。真实 profile 停止，原 12 Run 当前结果未读回，A0-V closure 继续冻结。W5c8q 文件级实施计划需先落实上述角色与测试，真实迁移/扫描/回填/ACK 另门。
