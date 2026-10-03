# E17-s3o-w-ao-b21｜忠实 ACL 克隆 Reader 私有登录验收

## 前提纠正及方案

- 已先读 b21 文件级方案、231-4/AIP-7/BIND-1、b17-b19 与旧 UI/configuration identity 部署脚本。b17 无网络忠实 ACL clone `aos-e17-b17-acl-pg`/`aos-e17-b17-acl-data`、库 `aos_e17_s3owaob17_acl_20261004@a0v_135` 仍 Up；b18 已有 Reader 角色且 `CONNECT=true`、DB ACL `Reader=c/aos_app`，独立本地 socket Reader 登录可读全局 Capability10。故原 D-waves 的“先 RED CONNECT”已被前波覆盖，不重复造 RED。
- `docker exec -u aos_aip_binding_readiness_reader` exit1 的报错是容器 OS passwd 没有该用户，非 PostgreSQL CONNECT拒绝；改用 `docker exec ... psql -U aos_aip_binding_readiness_reader` 验证。原 clone `pg_hba_file_rules` local all/all trust，Reader `rolpassword IS NULL=true`，即 b18 只证明独立角色/RLS，未证明私有凭据认证。

## 仅克隆改动及结果

- clone 内先将原 `pg_hba.conf` 以 mode600 保留为 `pg_hba.conf.b21-original`，新建 `b21-reader-private/` mode700、随机口令 passfile mode600；仅对该数据库/Reader 的本地 socket 新增首条 `scram-sha-256` 规则，原管理员/其他规则原样保留；`pg_reload_conf()` 返回 true。`docker exec ... sha256sum` 复核原副本 `2366fa203f80a6b335fb103ef2d181e5f9d2cebdd27ae5cff1eb97d991f94ff0`、新配置 `53bf1430376aa1004f8e0c6783f0a25eb016b4897dbac4fa44e9b5bad1233dad`，exit0。
- `pg_hba_file_rules` 首规则 `local ... Reader scram-sha-256` 无 error；`PGPASSFILE=/dev/null` 无文件 exit2，错误私有文件 exit2；正确私有文件独立登录输出 `session_user=current_user=aos_aip_binding_readiness_reader`、DB CONNECT=true、RegistryReceipt INSERT=false、全局 CapabilityRevision10、org-org/dev-project BudgetHead0，事务 READ ONLY，exit0。clone Reader 18 public表 SELECT/0写、17策略；Receipt6/CapabilityBinding0。原库 `BEGIN READ ONLY` 回读版本135、正式 Reader/issuer角色0、Receipt6/CapabilityBinding0，exit0。
- 为把凭据和 RLS 正反链合并，仅在 clone 由 postgres 插入唯一 `org-org/dev-project/b21-private-reader-rls-test-only-20261004` 合成 BudgetHead，`INSERT 0 1`；正确私有文件下独立 Reader 的同一 READ ONLY事务：无scope0、org-org/dev-project 1、dev-org/dev-project 0，exit0。随后精确 `DELETE 1` 只删该新造行，后读0；当前原库和 dev-org均无写入。该 test-only 行不作业务配置证据。
- 一次 clone 后验把安装表误写为不存在的 `asset_bundle_installation`，只读事务报错 exit1；随后 `pg_tables` 精确列出 `bundle_installation` 等表，改查 Receipt/Binding exit0。该失败不是数据损坏或迁移失败。

## 结论与风险

- 本波把 b18 的独立角色/RLS 与同一忠实克隆的私有文件 SCRAM 登录连成一条真实**test-only**链，仍是容器本地 socket/无网络，不等于当前 API `RegistryIssuerConnectionFactory` 或外部 OIDC正式验收；Reader passfile未复制到当前实例。clone pg_hba/Reader口令只在保留的隔离卷中改变，原文件副本可回滚；无原库角色/ACL/DDL/业务写、无 Host/worker/Provider。
- Capability issuer仍无正式角色和 operation scoped Receipt门，当前签名预览 b20 写503保持；正式 OIDC/API非owner/Owner、八配置/六 Binding/自然首链 pending。`org-org/dev-project`唯一正向，`dev-org`零副作用，不读商城源、不回放旧12 Run、不手工 Run、不碰230 L0、不 push。
- 下游最小合法生产者次序按 b14已验来源登记：Guard Data/Egress（E17-s3e）、Network（s3f）、BudgetPolicy与Budget（s3g）、Quota（s3h）、RuntimePolicy（s3i）各须在当前签名/审批/低权身份链实际签发，再由六个同事的正式 Model/Route/Eval→CapabilityBinding/SkillBinding 正向后审 frozen ResponsibilityPlan（s3j）。这些隔离 +1 试验与当前八候选0不可混同；本波不把列表本身当配置可用或启 Host 授权。
