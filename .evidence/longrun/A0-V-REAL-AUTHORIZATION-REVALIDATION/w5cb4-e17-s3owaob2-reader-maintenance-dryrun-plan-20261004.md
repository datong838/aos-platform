# E17-s3o-w-ao-b2｜Reader 当前角色维护前的默认只读预检方案

## 复习与定位

- 依据 231-4 的非 owner 专用角色、FORCE RLS、固定 search_path/超时/最小表权限，D-wave 2026-10-04 的克隆先行与当前库写入分门，以及 `aip_binding_readiness_reader_connection.py` 固定18表白名单。当前正式角色0；`aos_e17_s3owan_restore_20261004` 为已有独立 test-only 完整恢复克隆，源/克隆 head 都是135、clone public 592表、Reader role0。当前真实库仍只读。
- 现有 `e17_s3owan_restored_reader_probe.py` 是一次性 test-only 角色及 ACL 正反探针，末尾清理角色/policy；不得将它改名后直接用于当前库。维护 runner 需要更严格的固定 target、私有 admin 凭据来源、默认只读与可审计输出，且不能复用 test-only 凭据进入正式库。
- 实跑前复核修正：旧 s3o-w-an 恢复文档写 public sequence=11；2026-10-04 本波分别只读列出当前源与克隆 `pg_class relkind='S'`，两边12个名称逐项一致，`pg_sequences` 均12。维护预检按当前双端事实要求12，旧文档计数不再作为门值；保留首次按11失败关闭的证据。

## 文件级任务与安全门

1. 在 `services/aos-api/tests/aip/` 增维护预检的 RED：无显式 target、错误卷/库/head、Reader 已存在、18表不齐、任何租户表非 FORCE RLS、passfile 非0700父目录/0600本人文件、当前实例误选 apply 时均拒绝；默认路径不得有 DDL、DML 或 role/ACL 写入。断联后按只读状态对账，不能盲重试。
2. 最小新增 `scripts/a0v_e17_reader_maintenance.py` 的 **dry-run**：显式目标 `clone`，校验独立 test-only Docker context/容器/卷，固定数据库与135，验证18表形状、17租户表 FORCE RLS、角色不存在、已有同名 policy 不冲突、管理连接身份及备份恢复证据引用；输出不含密码的机器可读 gate 结果。此切片不加 `--apply-current`，也不自动 CREATE ROLE/GRANT/POLICY。克隆正反与故障测试通过后，再单独设计可回滚事务的 apply 切片。
3. 当前库切换是后续独立门：新一致全备及 SHA/TOC、独立全库恢复与安装/Receipt 摘要比对、API/Web/Host 零执行窗口、正式私有 Reader 密码文件与身份归属、事务性 DDL/GRANT/policy、只读 ACL/RLS/租户复核。任一缺失则不写当前库。现有当天 `dd3c8b99…129a` 备份尚未完整恢复，不能拿其 SHA/TOC 充当恢复演练。

## 完成判据

专项与相邻测试、克隆只读 dry-run 和异常负例、克隆前后 schema/role/policy/Installation/Receipt 不变；verification 落盘、m1 精确提交、01/06/D-wave/Prime 更新。完成 dry-run 只算维护预检控制面，不算正式 Reader 切换、API OIDC、八配置、Binding、Host 或自然首链。
