# s3o-w-ac 第一切片｜独立 BI rebind 的签名版本只锁门

## 依据与当前失败点

- 626、D-wave s3o-w-ac 与原 `SignedBIPlanActiveRebindService.rebind`/`SignedBIPlanActiveFreezeService.freeze`：两者在 active 安装锁及当前权限之后，用全局 `asset_bundle_version FOR SHARE` 锁住 Growth 发布行，再读取签名 resolver，防并发撤销越过同事务 Plan/Receipt。原签名全 schema owner 路径已正向；独立非 owner BI 登录对 Registry 四表 SELECT 全拒，不能借 runtime/owner 或宽表 GRANT。
- 当前真实库只读，预览栈已以最新 m1 19:53 重启；正式独立 DB 身份/role→scope+subject/IdP/六 Agent/当前发布仍缺。本波只在一次性库证明固定只锁函数与原服务的最小分支，不能宣称受限 rebind 全链或首链。

## 文件级步骤

1. `services/aos-api/tests/extension_runtime/plan_restricted_issuer_case.py`：在同一独立 BI 事务直跑原 `asset_bundle_version ... FOR SHARE`，记录 SQLSTATE42501 与全局表 SELECT=false；先写期待原 rebind 只锁动作可做的 RED。隔离函数 `public.aos_bi_plan_release_lock_a0v_139(org,project)` 只允许精确登录/租户 GUC，返回签名 Growth1.12/1.13 的版本主键并持 `FOR SHARE` 至事务结束；固定 search_path、SECURITY DEFINER，PUBLIC 收权，仅 BI EXECUTE。证明错租户/撤权拒绝、合法 Registry writer 并发更新在锁超时前不能越过。
2. `services/aos-api/aos_api/ecommerce_business_investigation_aip_authority.py`：仅当当前 DB 用户确为独立 BI 发行登录时，两处原 release 锁调用固定函数；其它身份保留原 SQL。不得改变 active 安装、原 Receipt、CAS、签名 resolver 的核验顺序。独立函数缺失/撤权必须失败关闭。
3. 签名全 schema 专项、相邻 BI/Receipt 回归、编译、代码/方案复审、verification、m1 精确提交与 AOS/Prime/D-wave。下一切片把隔离角色生命周期扩至原 active 安装后，核受限 rebind/Receipt 完整正反与有限进程未知结果只读对账；正式函数迁移需新备份+克隆全链+零执行窗口。
