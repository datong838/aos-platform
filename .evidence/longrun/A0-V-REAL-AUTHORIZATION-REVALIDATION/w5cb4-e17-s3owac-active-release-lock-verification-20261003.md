# s3o-w-ac 第一切片｜受限 BI 签名版本只锁门

## 方案与 RED

- 依同目录 `w5cb4-e17-s3owac-active-release-lock-plan-20261003.md`，原 rebind/freeze 在 active 安装检查后对 Growth 版本行 `FOR SHARE`；独立 BI 登录不能 SELECT 全局 Registry 表。签名 Growth1.13 一次性 full schema 克隆中，原查询 RED `psycopg.errors.InsufficientPrivilege: permission denied for table asset_bundle_version`，退出 1；Plan/Receipt 未因该测试重发。
- 最小实现仅把两处相同 release 锁聚合为 `_lock_growth_release`：普通原身份走完全相同的原 SQL，独立 `aos_bi_plan_issuer` 走固定 `public.aos_bi_plan_release_lock_a0v_139(org,project)`；函数缺失/撤权自然失败关闭。无当前库 migration/授权变更。

## GREEN 与风险复审

- Test-only 函数只在一次性库创建，返回 UUID 版本主键；固定 `session_user`、`org-org/dev-project` 与事务双租户 GUC，`SECURITY DEFINER`、`VOLATILE`（行锁所需）、`search_path=pg_catalog`，PUBLIC 无 EXECUTE，runtime 无 EXECUTE，仅 BI 登录可调用。原全局 Registry 四表 SELECT 仍全 false。测试 `FOR SHARE` 期间维护 owner 同行 UPDATE 在150ms锁超时，错租户与撤 EXECUTE 均报42501；测试函数/角色/库清理由原测试 finally/fixture 控制。
- 首次测试的函数签名误把 `version_pk` 写成 bigint，隔离库报 UUID 类型不符、退出1；按真实表类型改 UUID 后，原签名 full schema 最终 `1 passed`、退出0、13.07s。相邻 `test_ecommerce_business_investigation_aip_authority.py`、`test_aip_bi_plan_issuer_service.py`、`test_aip_responsibility_template_authority.py` 为 `71 passed`、退出0；目标 py_compile 和 diff check 退出0。
- 本切片只证明原两方法的共同 release 行锁分支和并发保护。独立发行登录下**完整 active rebind/Receipt 与 freeze 正向尚未跑**；原 owner full schema 全链通过不替代该证明。正式角色/函数 ACL 与 role→scope+subject 映射、IdP/六 Agent、当前安装激活与首链均缺。当前真库未写、Host/worker/Provider关。

## 下一门

- s3o-w-ad：将同一非 owner BI 测试身份延续到原生命周期 active 阶段，跑原 `SignedBIPlanActiveRebindService.rebind` 的受限 resolver、同键/CAS/回滚/撤权/并发和受限 rebind Receipt 正反，再接有限进程未知提交只读对账。正式迁移另需一致备份、全链克隆、零执行窗口；不得把 test-only 固定函数作为当前生产权限。
