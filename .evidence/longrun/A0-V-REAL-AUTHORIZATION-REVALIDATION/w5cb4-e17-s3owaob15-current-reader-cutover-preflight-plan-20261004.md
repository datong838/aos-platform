# E17-s3o-w-ao-b15｜当前 Reader/issuer 切换前置文件级方案

## 上位合同与当前事实

- 231-4、AIP-7 22、BIND-1 31 要求 Reader/issuer 独立非 owner 登录、精确同库而不同私有凭据，租户 RLS/最小 ACL 与正式 OIDC；当前原卷 `a0v_135`，Reader/Capability issuer role0、仓库 `.env` 正式 Binding/OIDC key0。b2/b3 的脚本仅有 clone/fresh-clone 模式，b3 全备完整恢复与 18表/17 policy 事务 apply/回滚已证；绝不把 test-only 登录接当前 API。
- 本波是**独立备份与当前切换前置**，不是借 test-only 脚本写当前库。缺正式 API OIDC 与可验证私有凭据时不执行当前库角色/ACL DDL、不启 Host/worker/Provider。

## 精确步骤

1. 只读核 m1 HEAD/唯一写者、原卷/库/迁移/签名 Receipt、8080/8434/18181 状态与测试 VM 容量；固定新备份目录 `aos-recovery/.aos-current-backup-20261004-s3owaob15`（只新建，0700）及新文件 `current-full.dump`（0600）。`pg_dump -Fc` 一致快照、fsync、SHA256、`pg_restore --list`；不删旧备份。
2. 在独立 test-only 卷仅新建 `aos_e17_s3owaob15_restore_20261004`；`pg_restore --no-owner --no-acl --exit-on-error` 全库恢复。源/克隆核 `a0v_135`、public表/序列、18 Reader 表与8安装/Receipt控制表的 count/稳定摘要；不写原库、不改既有测试库/卷。
3. 先用新克隆与原库的 18 Reader 表、8 控制表及 catalog **26/26 count/hash 相等**，结合 b3 同一迁移/表形状的 test-only Reader apply/失败回滚证明，收口本波**数据可恢复门**；不为重复测试制造第二套 test-only 角色。当前正式私有凭据另立来源和0600文件，不能复用 b3 test-only。写当前库前须另波在这份新克隆以拟用正式角色/ACL 协议复演，明确 API/Web/Host 零执行窗口、正式 Reader+issuer 身份/credential、OIDC issuer/JWKS/audience、精确回滚与安装/Receipt读回。任一缺则止于备份/克隆证据，继续可独立代码项。

## 退出门与风险

- 仅 `pg_dump`、完整恢复、26表摘要一致全部退出0才算本波数据安全门；b3 角色链是已证同形状依据，**不算本次正式切换通过**。备份文件本身或 TOC 可列不等于可恢复。克隆名称不存在才创建，失败保留现场供只读对账，不自动删除旧库/卷/备份。
- 真库维持只读，零正式迁移/Host/自然首链声明。org-org/dev-project 唯一正向，dev-org 零副作用；不读商城源、不回放旧12 Run、不手工 Run、不碰230 L0、不 push。
