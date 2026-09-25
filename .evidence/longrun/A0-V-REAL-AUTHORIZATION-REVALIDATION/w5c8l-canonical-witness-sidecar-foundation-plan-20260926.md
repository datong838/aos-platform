# W5c8l｜历史源组 canonical 见证 sidecar 基础计划

## 上位与停线

承接 W5c8j/k、`a0v_045` 与 AOS-000673。原 `pipeline_snapshot_group_claim/input` 三表自 `a0v_045` 起有 UPDATE/DELETE/TRUNCATE 拒绝触发器；为历史文本新增原表列并 UPDATE 回填将违反不可变边界。W5c8k 纯函数仅能在隔离夹具重建，尚无真实历史扫描。故本波先建立**空、不可变、运行角色不可写**的 sidecar 基础；不是历史回填、ACK 或真实迁移授权。

## 文件级清单

- 先读 `a0v_045` 不可变/RLS/索引与 `a0v_096` 撤权、W5c8k 见证代码，固定全租户双键、组 UUID、原 claim/input 双 hash 和文本上界。
- 新增 `services/aos-api/alembic/versions/a0v_097_snapshot_group_canonical_witness_sidecar.py`：单独空表 `pipeline_snapshot_group_canonical_witness_a0v_097`，精确 FK 指向原 claim/input 组身份，保存 binding/manifest 文本与原 hash，RLS、不可变 UPDATE/DELETE/TRUNCATE；初始不授 runtime/directory/maintainer INSERT、UPDATE 或 EXECUTE 写函数。迁移不查询或回填真实历史行，downgrade fail-closed。
- 新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c8l_witness_sidecar_foundation_pg.py`：隔离 PG RED→GREEN，验证空表、约束/触发器/角色权限、`SET ROLE aos_runtime` 无法伪造 INSERT，正常旧 claim/input 权限和 W5c8i 撤权不回退。测试数据库必须是 disposable `aos_test_*`。
- 新增设计 audit：后继 W5c8m 的逐行扫描需只读、限量、不可自动写；插入受控函数必须原表行锁/原 hash/双文本 parse+sha256/所有成员/租户及 Host-fence 设计完成，失败隔离。若基础表的 FK/RLS/权限不能同时证明，本波 STOP，不用宽权限修绿。

## 九步

1. 复习上位与真实冻结门、m1/AOS-000673、专用测试环境。
2. 本方案先提交，限定空表与零真实 effect。
3. 写隔离 PG RED：表缺失与权限/不可变负例。
4. 最小迁移，默认无运行角色写入口；不写回填或 ACK。
5. 专项与相关累计，测试库 0、静态检查。
6. 浏览器只读验收；无业务 UI/localhost 被阻断则标不可验收。
7. 方案/代码自洽与风险复审：原表不变、无权限扩大、真实库未迁。
8. verification 提交，D-waves/AOS CAS/Prime 强一致回读。
9. 自动下一波 W5c8m：先只读历史逐行扫描/拒绝矩阵，再设计受控 backfill writer；未经全链证明不建 ACK。

230 L0 挂起、商城源不读、dev-org 仅零 canary、unknown 不重发/不手工 `run_definition`；m1 单写不 push、不动其他分支。
