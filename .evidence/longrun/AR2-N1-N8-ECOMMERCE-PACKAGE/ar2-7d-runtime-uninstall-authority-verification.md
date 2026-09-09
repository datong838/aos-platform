# AR2-7D D6B2A runtime uninstall authority 验证

日期：2026-09-10
基线：`m1@806a9779`
结论：`AR2_7D_RUNTIME_UNINSTALL_AUTHORITY_GREEN`

## Rules 与实现结论

- 以 closure manifest、231-6 D6/C10/J04 和 D6 细化施工卡为权威；m1 单人串行、方案先行、最小实现、隔离 PostgreSQL、证据后提交；不 push，230 L0 挂起。
- `aos_app` 不获得 runtime 表的常规写权限，只能调用 `extension_runtime_uninstall_commit_ar2_018` 窄命令；`aos_runtime` 与 maintainer 均无执行权。
- 无 runtime binding 时命令严格 no-op；存在 binding 时锁定当前 active installation 与唯一 generation，并核验 disabled binding、成功 disable、D6A detached 与两份 Receipt、至少一项且全部已确认 released 的资源、三类未归宿义务为零、9/9 legacy dispatch 和 gate absent。
- 命令同事务写不可变 runtime uninstall Receipt，并把 binding 推进到 `uninstalled/stopped/fenced`。双向 deferred constraint 要求 Receipt、binding 与紧随其后的 installation `uninstalled` revision 同时成立，单独修改任何一侧都不能提交。
- Receipt `authority_data` 使用 PostgreSQL 内置 SHA-256 计算并由插入触发器复核；Python guard 逐项回读 tenant、installation、revision、actor 与数据库 hash。

## 修改文件

- `services/aos-api/alembic/versions/ar2_018_runtime_uninstall_authority.py`：新增窄命令、不可变 Receipt、hash guard 与双向终态约束。
- `services/aos-api/aos_api/extension_runtime/runtime_uninstall.py`：新增 `RuntimeUninstallGuard` 及精确 readback。
- `services/aos-api/tests/extension_runtime/test_ecommerce_growth_cutover_pg.py`：扩展真实迁移夹具，覆盖成功、no-op、未释放、缺 installation 终态、角色隔离和直接 binding 绕过。

## 验证证据

- D6B2A 专项：`6 passed, 57 deselected, 7 warnings in 4.91s`。
- 完整 ecommerce cutover PostgreSQL：`63 passed, 7 warnings in 18.79s`。
- Resource recovery 与 runtime lifecycle 邻接：`70 passed, 1 skipped, 7 warnings in 10.11s`。
- 测试启动的完整 Alembic 路径成功执行 `ar2_017 -> ar2_018`；Alembic 唯一 head 为 `ar2_018`。
- Closure：`1710 scanned / 93 classified / 57 migrated`，五类错误数组均为空。
- Memory validate：`AOS-000571 / GREEN / 865 Delivery Receipts / 2226 events / 846 Task Receipts`。
- Python compile 与 `git diff --check`：通过。

## 风险与保留边界

- 本切片只交数据库 authority 与 concrete guard；canonical HTTP 和 runtime control plane 尚未注入 guard，D6B2B 完成前不声称服务入口已封闭。
- 当前合同要求一个 installation 只能有唯一 runtime generation；出现多个 binding 时 fail-closed，D6C 重装必须使用新的 installation identity。
- 未执行真实 OCI 删除、真实租户卸载、共享/生产迁移、Provider、费用、发布或 push。D6B2B/D6C/D6D 仍待施工。

## 内容摘要

- `ar2_018_runtime_uninstall_authority.py` SHA-256：`6af65bd0a463fd18b3b74ece431d783d210dfd4c92f0163a4d18ed740aecad50`
- `runtime_uninstall.py` SHA-256：`54355fab05ae384e1b5e4fc19d2b92528f59f59daa935ae566731eaf48197ae4`
- `test_ecommerce_growth_cutover_pg.py` SHA-256：`e9497fab6f5e23a7b82c65c68dd1e87a071f2bdd997b6ab33ac2b35f011f6463`
