# s3o-w-ad 第一切片｜独立 BI active rebind 与 Receipt

## 方案、RED、最小修改

- 依据本目录 `w5cb4-e17-s3owad-restricted-active-rebind-plan-20261003.md`，仅在现有 Growth1.13 已签名、可销毁 full-schema 测试库中延续同一非 owner BI 登录及其准备 Plan 至原安装 active 阶段。原 owner Plan 与独立 BI Plan 分开，原 owner rebind/freeze 回归保留。
- 首次用无密码 DSN 运行测试，夹具连接 18435 报 `fe_sendauth: no password supplied`，退出1，未进入测试；改由原 `a0v_current_preview_bootstrap._connection_parameters()` 在进程内读取现有凭据，只给 `aos_test_*_ti4_test` 夹具，不输出密码。原 current DB 未写。
- 原受限 rebind RED：`CurrentControlPermission` 对经身份校验的 `_ScopedBIIssuerConnection` 误判为非 BI 登录，读取全局 `meta_membership` SQLSTATE42501，退出1。最小生产修改仅让该精确连接包装类型走已存在固定成员/marking 锁函数，并使原 prepare 的同类判断一致；普通 owner SQL、控制角色和租户判断不变。第一次错 ETag 反证期望错为 owner 的 `RevisionConflictError`，实际固定安装锁在 BI 登录下按合同报42501；修正测试期望，未改变生产门。

## 结果与一致性复审

- 显式 Growth1.13 本地签名回执、独立 PG/OCI、当前集群仅作创建/销毁一次性库的连接；原 full-schema 测试最终 `1 passed, 7 warnings`、退出0、12.32s。相邻 BI/Plan/权限回归 `71 passed, 49 skipped`、退出0，skip 为未设置 PG 环境的独立测试；目标 py_compile、`git diff --check` 均退出0。
- 同一独立 BI 登录先 prepare，active 后受限 `ActiveBIBusinessResolver.select` 返回精确签名版本；原 rebind 产生 Plan revision 与配对 Receipt，受限原 Reader 核原准备 Receipt、版本、Plan/签名 binding，同键重放同 revision。错 ETag 42501、缺准备 Receipt、dev-org、撤销 release 锁函数均失败关闭；test-only Receipt trigger 强制回滚后 Plan head 不动、rebind Receipt0；改参数同键冲突、改键旧 Plan CAS 拒绝；撤销成员只读函数后 Receipt Reader 42501。之前 s3o-w-ac 已单独证明 Growth 行锁对合法并发更新150ms超时，本波未重做双会话并发用例。
- 测试后在原集群只读核 `aos_bi_plan_issuer` 角色0、`aos_test_*_ti4_test` 库0，当前权威库 Alembic `a0v_135`。本波新增 fixture finalizer 在测试成功或失败后撤销凭据、函数、策略和角色；原安装生命周期的非 issuer Receipt 不再被测试守卫误拒。

## 尚未通过

- 这是隔离测试库的原方法正反，不是当前实例的正式独立发行。正式 DB 函数/ACL、role→scope+subject、外部 IdP、六 Agent、当前 Growth1.13 active 安装与八配置、Host assignment/binding 均仍缺；当前真实库只读、Host/worker/Provider 关、首条自然经营链 pending。有限私有进程未知提交只读对账、真实跨 UID、正式备份/全链恢复/零执行窗口留下一波。
