# W5CB4 E17-b｜00:49 备份隔离恢复对账（2026-09-28）

- 计划：`w5cb4-e17b-current-backup-restore-plan-20260928.md`。目标仅为 `aos-a0v-test-only/aos-a0v-test-pg` 新库 `aos_restore_20260928_e17b`，当前权威库只读。
- 前检：目标库 `SELECT count(*) FROM pg_database WHERE datname='aos_restore_20260928_e17b'` 为 0；VM 内 `sha256sum` 为 `cb2f1b63bee108ade2d20d4fa3b5583471332345111a02229db50ca43816533d`。
- 在隔离 PG 执行 `CREATE DATABASE aos_restore_20260928_e17b TEMPLATE template0` 退出 0；从原 dump 流式执行 `pg_restore -U aos_app -d aos_restore_20260928_e17b --no-owner --no-acl --exit-on-error --single-transaction` 退出 0，无错误输出。
- 使用同一只读 SQL 比较克隆与当前：克隆 `a0v_106`、public 表 566；当前 `a0v_109`、public 表 571。两者唯一安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813` 均 `approved/revision 3`，四个 published 包版本和四个摘要逐项相同，runtime operation/binding/assignment 均 0，六类来源 head 均 0。
- 判定：**旧截面逻辑恢复成功；“当前 a0v_109 可恢复”未获证明**。00:49 备份不得用于当前库的迁移安全门。旧备份和隔离克隆均保留，未对当前库执行任何写入、迁移、Host/worker 或业务命令。
- 下一动作：按修订计划从当前权威库新建独立只读 dump，另建隔离库完整恢复并对账；原 `a0v_106` 克隆不得复用或覆盖。
