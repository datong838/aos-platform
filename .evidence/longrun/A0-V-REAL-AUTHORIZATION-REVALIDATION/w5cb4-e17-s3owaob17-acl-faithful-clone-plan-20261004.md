# E17-s3o-w-ao-b17｜全局角色与 ACL 同形状新克隆文件级方案

## 上位方案与现场

- 231-4 规定非 owner 专用角色、最小授权、FORCE RLS 与显式租户；b16 只读发现 b15 `--no-acl` 恢复后共享 Receipt runtime INSERT 与原库不等。历史 bg00z 曾用保留 ACL 的新克隆复现权限漂移，不能重复把无 ACL 克隆当运行准入。
- b15 原卷 `a0v_135` 全备 SHA256 `e9038a51cee401e280d9dcfe4422f533cdb2fb407b00bd37bb21b6b5879bf498`，TOC 包含 ACL。只用此已核备份；新 test-only 库名 `aos_e17_s3owaob17_acl_20261004`，绝不覆盖 b15/其他克隆或当前库。

## 执行清单

1. 先只读核原卷/测试卷、备份 SHA/权限、目标库不存在和磁盘余量；比对 test-only 集群所需原角色名是否已存在，仅看名字/权限标记，不读密码。已见原集群的 `aos_a0v_*` 等角色在共享 test-only 集群缺失，故**不在该共享集群直接恢复 ACL**，也不为其全局补角色。新隔离实例固定 `colima-aos-a0v-test-only` 上新容器 `aos-e17-b17-acl-pg`、新命名卷 `aos-e17-b17-acl-data`、同版 `postgres:16-alpine`、`--network none` 不发布端口；仅 Docker exec 使用本地 socket，初始化 `postgres` 管理员并以 `POSTGRES_HOST_AUTH_METHOD=trust` 限在无网络实例。卷/容器保留供审计，不删除既有内容。
2. 当前原卷只读 `pg_dumpall --globals-only --no-role-passwords` 到新0700目录/0600文件并 SHA，**不含口令哈希**；在新实例以 `postgres` 应用角色/成员关系。仅在该实例新建目标 `TEMPLATE template0`、owner `aos_app`、撤 PUBLIC CONNECT；以隔离 superuser `pg_restore --exit-on-error` **保留 owner 与 ACL** 完整恢复。失败保留现场只读诊断，不覆盖/删除既有库/卷/备份。
   - 首次整份 globals 以 `postgres` 且 `-1` 应用在 `GRANTED BY aos_app` 处 exit3，事务已回滚且角色计数0。非 `GRANT` 行由 `postgres` 事务应用 exit0；原样显式 `GRANTED BY` 在此隔离集群即便 `aos_app` 自身或给 `postgres` ADMIN 仍 exit3、回滚。只在第二事务的内存输入中剥除每行尾部 ` GRANTED BY aos_app`，由**原授权者 `aos_app` 登录**执行相同角色、受者和 `INHERIT FALSE` 授权；先单条 `BEGIN/ROLLBACK` 已 exit0。保留原无密码 dump 不变，完成后比较 membership 与 grantor，并撤掉试探产生的 `aos_app → postgres` 临时管理成员关系。
   - 实测本隔离集群的 `pg_auth_members.grantor` 仍归 bootstrap `postgres`，即便以 `aos_app` 执行；这与原集群 `aos_app` grantor 不同。只在本新实例事务内撤临时 `aos_app → postgres` 并重授10条原角色/受者/选项，复核**有效成员关系**一致；grantor 差异明确保留为元数据限制，不声称全量 catalog 完全相同。
3. 原库和新库各 `BEGIN READ ONLY`：核迁移、592表/12序列、26表数据摘要、Reader/issuer 角色、共享 Receipt 和关键 Reader/发行表表级 ACL/默认 ACL/RLS。仅有效角色关系、表级与默认 ACL、Owner/RLS 等形才可在此克隆运行后续 issuer 负门；bootstrap 导致的 membership grantor 差异单列限制，不由克隆证明正式凭据、外部 OIDC、Owner 或零执行窗口。
   - 首次恢复后26/26数据一致，592表中13张仅 `relacl` 为源 `aos_app=arwdDxt/aos_app`、克隆 NULL（owner 隐含全权），另1张 ACL 条目顺序不同；按角色名展开的**有效**604关系（592表+12序列）ACL/owner/RLS 已 604/604 一致，不为文本顺序造授权。函数审计发现 `pgcrypto` 36函数由恢复时的 bootstrap `postgres` 持有、源均 `aos_app`；单函数 `BEGIN/ROLLBACK` 改 owner 可行。仅在新克隆事务性把这36个明确扩展成员函数 owner 改为 `aos_app`，再复核函数 ACL/owner；不得对当前库改授权。
4. 专项为新恢复与双端只读对比；无生产代码/UI变更不重复浏览器。落 verification、精确提交、AOS/Prime/D-waves 同步后进入下一独立主线。

当前真实库只读、Host/worker/Provider关；`org-org/dev-project` 唯一正向、`dev-org` 零副作用；不读商城源、不回放旧12 Run、不手工 Run、不碰230 L0、不 push。
