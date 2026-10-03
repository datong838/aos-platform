# s3o-w-p 第一切片｜原签名 BI 安装锁接线

- 基线：AOS `m1@5ddcfb19`、Authority `AOS-001228`、代码/当前库头 `a0v_135`；本切片当前真实库只读、Host/worker/Provider关闭，未创建正式身份或迁移。
- 上位方案与文件级计划：`231-3`、D-wave s3o-w-p、`w5cb4-e17-s3owp-bi-original-transaction-plan-20261003.md`。原 `FOR UPDATE/FOR SHARE` 需 UPDATE 权限，BI 专用角色不能直接取得。
- RED：在一次性原签名 Growth1.13 全 schema 库给非 owner BI login 安装表及其不可变读取依赖精确 SELECT/RLS，并建仅此登录可 EXECUTE 的 test-only 锁函数；原 prepare 仍在 `bundle_installation` 行锁 SQLSTATE42501 失败，测试 exit1。Plan/BI Receipt0。
- 最小改动：`PostgresInstallationStore.lock_for_bi_plan_in_transaction` 仅对精确 `aos_bi_plan_issuer` 调用受控安装锁函数，随后无锁读取原不可变安装历史；其他数据库角色仍走原 Store 锁。原 BI prepare/rebind/freeze 三入口接此方法。函数/角色仍只在测试一次性库创建，当前库函数0、角色0；缺函数的正式路径失败关闭。
- GREEN 范围：原签名全 schema 测试独立 `1 passed`、exit0；BI prepare 在真实获准 test-only 安装后通过安装锁、原记录/签名读，下一拒绝为 `meta_membership` 的 `FOR SHARE` SQLSTATE42501，BI Plan/Receipt 仍0。原安装 writer 与该锁在同一行冲突，150ms lock_timeout 拒绝并且安装 ETag 未变；错租户/错 ETag 拒绝。旧 BI、安装 Store/Service、独立锁与身份相邻测试 `48 passed`、exit0。`py_compile`、`git diff --check` exit0。
- 当前只读复核：`a0v_135/a0v_135`；测试角色0、`aos_test_*_ti4_test` 临时库0、正式锁函数0、org-org/dev-project 当前 Plan0。未读取商城源或触发 Run。
- 复审与风险：原 `CurrentControlPermission` 还对 `meta_membership`/`authz_tuple` 使用 `FOR SHARE`；直接授 UPDATE 违反最小权限。下一切片先设计受控权限读取/锁函数并在原签名全 schema 证明角色、marking、撤销并发、失败回滚；正式安装锁与权限函数 migration、凭据、当前库备份/克隆/零执行切换独立波。不能将本波 SQL 接线当 BI Plan 正向或业务首链。
