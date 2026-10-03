# E17-s3o-w-ao-b17｜当前135角色/ACL有效等形隔离恢复验证

## 目标与来源

- 原卷 `colima-aos-extension/aos-a0v-recovery-pg-data`、库 `aos_current_preview_20260927@a0v_135` 全程仅 `pg_dumpall`/`pg_dump` 与 `BEGIN READ ONLY`；b15 全备 `/Users/ddt/work/projects/ai_agent/aos-recovery/.aos-current-backup-20261004-s3owaob15/current-full.dump` SHA256 `e9038a51cee401e280d9dcfe4422f533cdb2fb407b00bd37bb21b6b5879bf498`。
- 新独立目标 `colima-aos-a0v-test-only/aos-e17-b17-acl-pg`，`postgres:16-alpine`、`--network none`、新卷 `aos-e17-b17-acl-data`、库 `aos_e17_s3owaob17_acl_20261004`。`docker inspect` 回读网络 none、唯一该新卷、Running=true；没有碰 b15 克隆或旧库/卷/备份。

## 操作与复核

| 门 | 结果 |
| --- | --- |
| 角色无密码备份 | 原容器 `pg_dumpall -U aos_app --globals-only --no-role-passwords` exit0；新0700目录、0600文件 `aos-recovery/.aos-current-backup-20261004-s3owaob17-acl/globals-no-password.sql`，5249字节、SHA256 `7e4aa77c1ba4546d782bede1516d978bd65675ada98bf2d87001daf71075087a`；不含 `PASSWORD` 关键字/口令哈希。 |
| 角色导入失败闭合 | 原 globals 全文由新集群 `postgres` 单事务导入因显式 `GRANTED BY aos_app` exit3；回读 `aos_app` 角色0，证实回滚。非 `GRANT` 行由 `postgres` 事务导入 exit0；同10条成员关系去掉显式 grantor 后由 `aos_app` 导入 exit0。为诊断临时给 `postgres` 的管理成员关系撤销需 CASCADE；在单事务撤销并重授10条 exit0。当前源/克隆有效成员关系均10、差异0，但克隆 `pg_auth_members.grantor=postgres`，原库为 `aos_app`，此元数据差异未消除。 |
| 保留 owner/ACL 全库恢复 | 新库先 `CREATE DATABASE … OWNER aos_app TEMPLATE template0`、`REVOKE CONNECT … FROM PUBLIC` 各 exit0。b15 全备以新实例 `postgres` 执行 `pg_restore --exit-on-error --single-transaction`，**未**使用 `--no-owner/--no-acl`，exit0、stdout/stderr 均0。 |
| 数据与关系权限 | 原库/新库各 `BEGIN READ ONLY`：均 `a0v_135`、592 public表/12序列、Reader/Capability issuer role0；18 Reader＋8安装/Receipt控制表 count/排序 JSONB 摘要26/26一致、mismatch0。604关系（592表＋12序列）按角色名展开 `aclexplode(coalesce(relacl,acldefault))`，连同 owner/RLS/FORCE RLS 604/604一致；默认 ACL 两条一致。原始 `relacl` 文本14项不同，其中13项是 owner 全权显式记录与默认隐式全权、1项是顺序不同，**有效权限无差异**。 |
| 扩展函数 owner | 初次恢复 `pgcrypto` 36函数归 bootstrap `postgres`，原库36个均归 `aos_app`；单函数 `BEGIN/ROLLBACK` 修正可行，后在新库仅对这36个精确扩展成员函数事务性 `ALTER FUNCTION … OWNER TO aos_app` exit0。public函数 owner＋按角色名展开有效 ACL 318/318一致、mismatch0。 |
| issuer 负门原样复现 | 原库与新库的 `has_table_privilege('aos_runtime','public.aip_agent_registry_receipt','INSERT')` 均 true，SQL各 exit0；b15 无 ACL 克隆为 false。现有 `RegistryIssuerConnectionFactory` 要求 false，因此当前发行身份仍应失败封闭；不得为了 clone GREEN 全局撤 runtime INSERT。 |

## 复审与边界

- b17 证明了新隔离实例的**有效**角色/ACL/RLS、关键数据与当前原库等形；不宣称 `pg_auth_members.grantor` 字节级同形。恢复用 bootstrap `postgres`、无网络，仅审计/测试；现有正式私有 Reader/issuer/OIDC/Owner 仍缺，role0、八配置/六 Binding/首链 pending。
- 本波没有生产代码、迁移、API/Web/UI 或当前库写入；专项是全库恢复和双端只读对比，无页面变化所以不重复浏览器/前端回归。方案步骤、失败回滚和实际修正一致；原库保持只读，Host/worker/Provider关。下一波先针对共享 Receipt 的 operation scoped 授权、正式身份来源和可独立配置生产者列最小实现点，不能直接当前库切换。
- `org-org/dev-project` 唯一正向、`dev-org` 零副作用；不读商城源、不回放旧12 Run、不手工 Run、不碰230 L0、不 push。
