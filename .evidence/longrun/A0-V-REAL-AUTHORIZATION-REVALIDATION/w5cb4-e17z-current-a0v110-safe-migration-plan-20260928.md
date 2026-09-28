# W5CB4 E17-z｜当前卷 a0v_110 安全迁移独立波方案

## 先决事实与边界

231 主计划、240 每日重启门及 E17-y2 verification 已复习。`m1@4ba2d80c` 的唯一代码头为 `a0v_110`；当前权威库 `aos_current_preview_20260927` 在 `aos-a0v-recovery-pg-data` 中仍 `a0v_109`。8080/8434 当前 200 只是旧进程。旧 `scripts/a0v_safe_fullstack_recovery_clone.py` 硬编码 `aos_meta_head@a0v_092→106`，不得用于当前库。

## 顺序与退出条件

1. 只读确认 `m1` 唯一写者、HEAD、工作区精确差异、原 PG 容器与命名卷、库版本/安装/签名 Receipt、API/Web/Host 端口；无误再做下一步。
2. 在源库 REPEATABLE READ READ ONLY 下导出快照，以 `pg_dump -Fc --snapshot` 生成新的 0600 备份，fsync、SHA256、`pg_restore --list`；禁止覆盖或删除现有备份。
3. 建独立新库并 `pg_restore --exit-on-error`；核对迁移版本、所有原 public 表行数摘要、安装/包签名与运行零绑定；先只在克隆 `a0v_109→110`，验四表 ACL/RLS/不可变、当前 owner 与 active 预算状态、原表行数不变。恢复/迁移失败保留现场，只读诊断。
4. 当前库切换是独立判定：须有明确零执行窗口、正式备份恢复链和精确代码/库一致。任何权限/签名/身份/连接不确定即停在克隆，不强迁移或重启新 API。若条件齐备，源库迁移只允许 append-only `a0v_110`，先关闭旧 API/Web、保持 Host/worker/Provider 0，迁移后最新 m1 全面重启 DB/API/Web；逐项回读版本、卷、健康、安装、禁入、八页基础访问和核心只读功能。不得手工 Run、读商城源或写 `dev-org`。

## 文件与验证

克隆演练后发现 `scripts/a0v_current_preview_http.py` 的 `EXPECTED_SCHEMA_HEAD` 和 `services/aos-api/tests/extension_runtime/test_a0v_current_preview_http.py` 均硬编码 `a0v_109`。本波在源库迁移前，先把测试改为期待 `a0v_110` 并观察 RED，再仅修改上述脚本常量；隔离测试与签名预检按边界验证。旧 bootstrap/registry/installation 初始化脚本保持历史目标不改。证据写本目录 verification、上下文 268、D-waves 清单；精确 m1 提交，memoryctl CAS 更新。下波继续正式费用上界与原子预算消费。
