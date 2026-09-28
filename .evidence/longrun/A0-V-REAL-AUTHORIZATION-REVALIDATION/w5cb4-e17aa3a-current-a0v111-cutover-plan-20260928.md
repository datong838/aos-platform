# W5CB4 E17-aa3a-cutover｜当前权威卷 a0v_111 独立切换方案

## 权威与前提

复用 E17-z 安全迁移方案与验证、231 主计划和 240 每日检查门。`m1@7f4ab6cf` 代码头 `a0v_111`；签名安装预检当前 `aos_current_preview_20260927@a0v_110`、approved 安装 1、四个 published 包、runtime binding 0；PG 原容器挂载 `aos-a0v-recovery-pg-data`。本次只加 active BudgetRevision 禁入触发器，当前 active 预算为 0。Host/worker/Provider 不启。

## 顺序

1. 再核 m1 单写、精确工作区差异、原卷、库版本、签名安装和端口；备份到新的 0700 目录/0600 文件。用源库 REPEATABLE READ READ ONLY 导出快照，再 `pg_dump -Fc --snapshot`；fsync、SHA256、`pg_restore --list` 均通过。
2. 独立新库完整 `pg_restore --exit-on-error`。逐张原 public 表行数摘要、版本、安装、签名包、绑定、预算行对源库一致；只在克隆 `a0v_110→111`，再核原表行数守恒、trigger 生效、`aos_runtime` 直写 active 失败和 Draft 不受影响。克隆失败保留现场，源库不动。
3. 零执行窗口：停 API/Web，确认 8080/8434/18181 无监听、当前 DB 无非空闲会话、备份仍同 SHA。源库只做单步 additive `a0v_111`；读回版本、原表行数、安装/签名/绑定及 active 0。失败保持服务关闭并只读排障。
4. 重启原 PG 容器并核卷。将 `scripts/a0v_current_preview_http.py` 的固定版本和对应测试从 `110` 改为 `111`，测试先 RED 再 GREEN；用最新 m1 API 及 8434 Web 重启，签名预检、健康/就绪、八页基础路径与只读核心功能回读。18181/Host/worker 仍关闭；HTTP 200 不当业务闭环。

## 边界和证据

当前源库仅在第 3 步完成前置门后迁移；不读商城源、不写 dev-org、不重放旧 Run、不手工 run_definition、不删除旧库/卷/备份。`test_ecommerce_content_review_pending_pg.py` 有独立未提交改动且固定旧版本，本波不编辑或纳入提交；累计门如仍失败原样记录。新增 verification、D-waves、上下文，m1 精确提交。若任一步不能证明，停止源库切换并保留复核入口。
