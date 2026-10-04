# b50｜命令先提交、Registry 撤销等待（文件级计划）

基线 `m1@6e3e39d8`、AOS-001308，当前真实库135只读。复习 231-3 安装生命周期锁、BIND-1 当前依赖/CAS/Receipt、b48/b49 完整 signed Growth1.13 disposable PG/OCI 负门。

## 精确问题与顺序

b49 只证 Registry revoke 持 advisory、评估等待后旧快照必须失败。反向需证评估先在受限命令事务持安装锁与 Registry advisory、产生未提交 blocked Receipt；正式 `RegistryService.revoke` 应等待；评估提交时 release 尚 published，Receipt恰一条，随后撤销合法提交。撤销提交后再用旧来源调用必须拒绝且不能追加第二 Receipt。这个次序不证明正向 available 或自然首链。

## 文件与 RED/验证

1. `services/aos-api/tests/extension_runtime/plan_restricted_evaluate_case.py`：增 test-only reverse branch，以真实 producer 在线程发 revoke、用 `pg_locks` 确认等待 advisory，评估事务提交后回读 Registry revoked、Binding CAS 与唯一 Receipt，再重试旧来源核无半写；线程/SQL 超时和 finally 清理。
2. `services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py`：新增独立环境 `AOS_B50_EVALUATE_FIRST=1` 控制此克隆路径，以避免撤销污染默认测试。先让测试要求反向行为（RED 可以是路径缺失/断言失败），再做最小 helper 实现；不改生产服务/迁移。
3. 复跑 b49/b48/默认三个完整 signed 模式和 b37/b45/Release 相邻回归，写 verification。另核原 Installation producer 的 active→换代前置条件；若需另外当前 RuntimeOperation 权限/卸载授权，本波不拿 admin 直改头假造正式路径，在下一波按原生产者构造独立克隆。

## 权限与限制

b49 `FOR SHARE` 在 PG 上要求 test-only NOLOGIN definer 的 release `status` 列级 UPDATE；当前 caller 只有 EXECUTE。正式可部署命令不得未经权限审查照搬，该角色不能是普通 runtime/issuer。可信 available 仍需实际签名字节/信任根、evidence freshness 与八类依赖同最终事务，DB 可验证 evaluator 身份；本波仅 blocked 负/序列化门。Host/worker/Provider关闭，不动真库、不读商城源/旧Run/230 L0、不 push。

实施边界：原 Installation active→uninstall/rebind 与当前 RuntimeOperation 的合法前置仍需独立审计，本波未造 admin 直接更新 ETag 的假换代测试，结转 b51；反向 Registry 顺序已用原 producer 的真实撤销测试。
