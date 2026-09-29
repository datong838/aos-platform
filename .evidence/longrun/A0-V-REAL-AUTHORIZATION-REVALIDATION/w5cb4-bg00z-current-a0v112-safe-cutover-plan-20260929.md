# W5CB4 BG-00z｜当前库 a0v_112 安全切换文件级方案

## 进入事实与边界

`m1@4904cced` 的唯一 Alembic 新头为 `a0v_112`，仅新增四张默认空 Eval authority 表；BG-00y 新克隆专项 `5 passed`、相邻 `27 passed`。当前权威卷 `colima-aos-extension/aos-a0v-recovery-pg-data`、库 `aos_current_preview_20260927` 仍 `a0v_111`；原 API 8080 PID 39708、Web 8434 PID 8355 在运行，18181 无监听。`scripts/a0v_current_preview_http.py` 的精确版本门和相邻测试仍为 `a0v_111`，须最小更新。旧版只读签名预检 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`：栖月汇 approved 安装 1、published bundle 4、Runtime Binding 0，退出 0。产品主计划 231/231-4 要求共享 schema 受控串行迁移、单一事实权威、FORCE RLS、可恢复与零执行窗口。

## 文件级最小改动与 RED

只改 `scripts/a0v_current_preview_http.py` 的 `EXPECTED_SCHEMA_HEAD` 为 `a0v_112`，以及 `services/aos-api/tests/extension_runtime/test_a0v_current_preview_http.py` 的同一断言。先把测试断言改到 `a0v_112` 得到 RED，再改脚本为 GREEN；签名、安装、worker 禁用、端口和 tenant 门保持原算法。关联证据 `.evidence/.../w5cb4-bg00z-*-{plan,verification}-20260929.md`、docs 301、D-wave。

## 零执行窗口与备份克隆

1. 停止 API/Web 并确认 8080/8434/18181 无监听，Host/worker/Provider 本来关闭；只读确认当前卷、数据库、`alembic_version=a0v_111`、安装/签名制品/Runtime Binding 与目标库内未完成 Eval。无 API/worker 进程后从当前 PG 做全库 custom-format `pg_dump` 到新的独立目录，以临时文件写完后原子命名；记字节数、SHA256、`pg_restore --list` TOC。保留今日 09:04 备份及所有历史库/卷。
2. 在 `colima-aos-a0v-test-only` 新建唯一数据库，从**新备份** `pg_restore --single-transaction --exit-on-error`，比对版本、public schema 数量、非商城源安装/制品表的逐行摘要与 Eval/Binding 零状态，再仅克隆升到 `a0v_112`。复核四新表空、RLS/FORCE、运行角色仅 SELECT；新克隆不插入正式签发/业务数据。失败保留克隆只读诊断，不迁当前库。
3. 用当前 bootstrap 的真实连接参数核对库名与卷，在仍无 API/Web/Host/worker 的窗口中执行 `alembic upgrade a0v_112`；`a0v_112` 是 additive transaction DDL，失败应保持 `a0v_111`。成功后当前库回读 `a0v_112`、四表空、原安装/制品摘要不变、Runtime Binding 0。任何漂移不启 Host/worker/Provider。
4. 新脚本的签名 Receipt 预检应对当前库返回 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`；用最新代码重启 API 8080 和 Web 8434，验证健康/就绪、端口、安装/签名、Skill 页面与业务禁入。浏览器只读验收沿 browser-pilot，不产生 Run。Runtime Host 18181 持续关闭。

## 失败处理与退出

迁移前失败：保持当前库 `a0v_111` 与新备份，不用高头代码启动；先定位并修复。迁移失败：Alembic 事务回滚并读回版本/原表摘要后才可用旧版本门重启。迁移成功而服务失败：保持零执行，先以新克隆和日志定位最小修复；若需要回退，只能从已验证新备份恢复到**另一个**隔离目标并裁定连接切换，不破坏当前卷，不静默 downgrade。成功退出要有新备份 SHA/TOC、独立新克隆恢复+迁移、当前迁移与 latest PG/API/Web 全部回读、专项/邻接测试和禁入状态证据。此波只切 schema 与服务版本，不创建正式 G2 issuer/Owner，不启首链。
