# E17-s3o-w-ao-b3｜新鲜恢复克隆 Reader 事务 apply/回滚文件级方案

## 上位合同与现时事实

- 复习 231-4 非 owner 最小 SELECT/FORCE RLS、BIND-1 31 与 D-wave 2026-10-04；b2 已有 clone-only 只读 dry-run，当前真实库仍只读、正式 Reader/issuer role0。b2 老克隆留有 test-only EvidenceBundle 行，不作为正式切换演练输入。
- 新独立目标固定 `colima-aos-a0v-test-only/aos-a0v-test-pg` 新库 `aos_e17_s3owaob3_restore_20261004`；创建前只读确认数据库不存在，目标卷与当前 `aos-a0v-recovery-pg-data` 不同。当前源 `aos_current_preview_20260927@a0v_135`，代码唯一 head135；本波不修改当前库，不停 API/Web/Host（Host 本来关闭）。

## 串行步骤

1. 在私有 `aos-recovery/.aos-current-backup-20261004-s3owaob3/` 以当前命名卷 `pg_dump -Fc` 做新一致全备并 fsync，记录字节/SHA和 `pg_restore --list`；若目标文件/库已存在，先只读对账并退出，不覆盖、不删除。独立 test-only 库 `CREATE DATABASE TEMPLATE template0`、撤 PUBLIC CONNECT，仅向新库 `pg_restore --no-owner --no-acl --exit-on-error`。源/克隆版本、592表/12序列、18 Reader 表与8安装/Receipt 控制表行数和内容摘要逐项比较。恢复失败保留现场，不重试覆盖。
2. 先在 `services/aos-api/tests/aip/` 做事务 apply 的 RED：错误库/身份、角色已存在、白名单缺表、FORCE RLS 缺失、策略冲突、异常注入回滚、重复执行只对账不重建；复用 s3o-w-an 已有错误凭据/额外权限负例作相邻回归。只在 `scripts/a0v_e17_reader_maintenance.py` 增显式 clone-apply 子命令，固定新鲜克隆和私有 test-only 临时 Reader 凭据；事务内建 NOINHERIT/NOBYPASSRLS 非 owner LOGIN、18表 SELECT、17张租户表精确策略，任何一步失败整体回滚。不得增加 current/apply-current 模式。
3. 在新鲜克隆跑原 `ReadinessReaderConnectionFactory` 独立登录、18表 SELECT、无额外读写/owner/runtime、策略17和同租户空态；原 s3o-w-an 恢复克隆已有 frozen exact/错租户/撤销正反链，作为相邻证明而不向新鲜恢复库插入 test-only 业务行。故障负例后 role/policy必须0。因 test-only PG 的角色是集群全局对象，会影响其它测试，成功演练证据读回后按精确对象清理本波新建的 test-only policy/role，再证 role/policy=0；保留新库与全备供只读对账，不将 test-only 凭据接当前 API。
4. 专项/相邻测试、`py_compile`、diff check、方案/代码复审、verification、m1 精确提交，AOS/Prime 与 D-wave 同步。脚本只涉及 test-only 数据库，浏览器不适用；当前正式 Reader/OIDC/issuer/Owner/八配置/首链 pending。

## 当前库切换另门

即使 b3 新鲜克隆 apply 全绿，当前库角色/ACL 写入仍须另取切换前新备份并完整恢复、正式私有凭据来源、API/Web/Host 零执行窗口、当前安装/Receipt 摘要比对和可回滚操作。任何条件缺失只阻该实例，继续其他安全研发。
