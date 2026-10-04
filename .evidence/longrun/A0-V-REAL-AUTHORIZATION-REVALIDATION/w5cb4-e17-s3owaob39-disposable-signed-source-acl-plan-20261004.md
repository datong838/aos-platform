# E17-s3o-w-ao-b39｜隔离签名安装的非 owner 来源 ACL 施工计划

## 上位合同和 b38 输入

- 231-2/3/4 与 BIND-1：最终 active/run 必须 current active 签名安装、Registry 撤销与精确依赖在一个受控事务重验。b37 内部 Reader 只是证据；b38 实测当前正式 issuer/Reader 登录角色不存在，不能在原库做正向。
- 原 Reader 精确需要四安装/锁表 + 四 Registry/证据表 SELECT。Installation 四表强制 RLS，Registry 四表全局发布证据。现有 `aos_runtime` 对八表还可 UPDATE，不是可接受的发行身份。本波只能在完整迁移 disposable PG/OCI 的 Growth1.13 **test-only**签名 active 安装上验证最小权限可行性；当前原库保持只读。

## 文件级最小步骤

1. 在既有 `services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py` 的 Growth1.13 已 active 段，用同一可销毁数据库创建随机非 owner、非 runtime 的 **test-only 登录角色**。先不授来源表 SELECT，调用 b37 `_read_unique_active_in_transaction` 并断言缺权限拒绝，随后单项期待最小权限正向先跑 RED。角色在 `finally` 精确 `DROP OWNED`/`DROP ROLE`，不改当前原库。
2. 仅在该 test-only 数据库对八表 `GRANT SELECT`，对四安装/锁表建 org/project GUC 约束的角色专属 RLS policy；不得授 INSERT/UPDATE/DELETE、`aos_runtime` 成员或 schema CREATE。用独立登录、SERIALIZABLE 事务核同租户签名 active 正向、错租户/错 hash 失败及连接未提交；来源视图依旧 `EVIDENCE_ONLY_NO_START`。没有正式 issuer/绑定写权，本波只证来源读取 ACL，不宣称最终激活已闭合。
3. 串行专项 full-schema OCI、原 Reader/相邻 AIP 测试，检查角色 cleanup、方案/代码一致性、静态检查。若低权读取还需额外表或权限，以实际 `InsufficientPrivilege` 逐项扩充最小集合并记录；不得高权捷径。

## 后续

- 下一门仍需 issuer 当前正式凭据、低权 Binding UPDATE/Receipt INSERT、安装行 `FOR SHARE`、Registry advisory `(228,1)`、撤销/换代并发 RED 及最终 CAS；若新迁移必需，另立独立备份+全恢复克隆+零执行窗口的当前卷切换。b34/b37 xfail、当前实例禁入保持。
