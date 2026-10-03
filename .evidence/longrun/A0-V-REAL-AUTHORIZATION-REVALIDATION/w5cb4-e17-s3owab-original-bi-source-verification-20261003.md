# s3o-w-ab 第一切片｜原 BI prepare 与受限 Receipt 回读验证

## RED 与修复

- 按同目录 s3owab plan，原 prepare 改用上一波的受限签名 resolver：初次隔离全链退出 1，`exact signed approved BI installation unavailable`。核对发现测试用 0600 passfile 的 TemporaryDirectory 在写事务前已退出，导致 resolver 失败关闭；把测试私有目录生命周期延至原方法结束，复跑全链 1 passed。未切回 owner resolver。
- 随后原 `SignedBIPlanReceiptReader` 用同一非 owner BI 只读连接回读，RED `psycopg.errors.InsufficientPrivilege: permission denied for table meta_membership`，退出 1。先修订方案，再为两个原 BI Receipt Reader 加显式受限 scope 分支，固定调用 `public.aos_bi_plan_membership_read_a0v_138`；默认直查表逻辑不变。一次性库 test-only 函数只返栖月汇测试主体成员角色，`STABLE/SECURITY DEFINER/search_path=pg_catalog`，PUBLIC 无 EXECUTE、BI 登录独享。

## GREEN 与负例

- 当前签名预检连接下，显式 PG/OCI 测试门+本地 Growth1.13 签名回执的原 full schema 一次性库测试最终 `1 passed`、退出 0、10.64s。受限签名 resolver 下原 `SignedBIPlanPreparationService.prepare` 产生 Plan 和配对 prepare Receipt，同键回放不增行；独立只读 Receipt Reader 核原 Plan ref、安装绑定与 actor。没有当前真实库写入。
- 同一测试证明 BI 登录没有 `meta_membership` SELECT、四张全局 Registry 表仍无 SELECT；错租户、另一 subject、撤回函数 EXECUTE 失败关闭。rebind Reader 在同一受限连接对不存在的 rebind Receipt 得 `ProductionContractNotFound`，未伪造 rebind 正向。
- 相邻 `test_aip_bi_plan_issuer_service.py`、`test_aip_bi_plan_issuer_connection.py`、`test_w2a_production_contract_store.py`、`test_w2b_production_contract_store.py`：39 passed，退出 0；目标 py_compile、diff check 退出 0。

## 界限与下一切片

- 正式库没有该函数/ACL，当前 HTTP 写口仍 503；测试私有 passfile、硬编码 subject 与一次性角色不能当正式凭据和 role→scope/subject 合同。原 rebind 正向、完整受限有限进程、真实不同 UID、未知提交只读对账、当前正式六 Agent/IdP 仍待证。不能以 clone 绿灯宣称 Growth1.13 当前发布或首链成功。
- 下一切片 s3o-w-ac 先复习原 rebind 与 active 安装/签名锁边界，隔离库 RED 后仅做可授权的受限原链正反；再接有限进程和未知结果只读对账。当前 DB 迁移另需一致备份、全链克隆、零执行窗口，Host/worker/Provider保持关。
