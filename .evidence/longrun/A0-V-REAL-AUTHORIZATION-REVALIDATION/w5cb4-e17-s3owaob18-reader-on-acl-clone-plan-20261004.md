# E17-s3o-w-ao-b18｜有效 ACL 克隆上 Reader 独立登录与 RLS 文件级方案

## 复习与纠偏

- 231-4、AIP-7 22、BIND-1 31 要求非 owner、FORCE RLS、精确租户、最小表授权。b3 `a0v_e17_reader_maintenance.py` 只认旧 test-only 容器/卷/5433/备份，不存在当前库写模式；b17 克隆为新卷且 `--network none`，直接复用旧脚本必以目标身份门拒绝，不能改成宽泛命令行目标绕过隔离。
- b17 已证当前原库与新克隆 26表数据、604关系和318函数有效权限同形；`aos_runtime` 对共享 Receipt INSERT 仍 true。该权限冲突只阻 issuer，不妨碍 Reader 只读角色 test-only 验证。

## 精确施工与验证

1. RED：原维护脚本在 b17 新容器/库前必须以 `READER_CLONE_TARGET_REQUIRED` 或 exact target 拒绝；只读核新库 `Reader role0/policy0`、18表形状、17张 FORCE RLS、安装1/Receipt6。若与 b17证据不符即停。
2. 仅在 `colima-aos-a0v-test-only/aos-e17-b17-acl-pg` 通过 `docker exec psql` 的本地 socket，由 owner 开一事务创建固定 Reader 登录/18表 SELECT/17租户 SELECT policy；在第5条 policy 人为失败、ROLLBACK，核角色/policy仍0。再正向提交，并由**独立 session_user Reader**（容器内连接，非 `SET ROLE`）读全局 Capability目录和 `org-org/dev-project` 租户表；无租户/`dev-org` 仅零副作用读，跨租户结果不得可见，写权限0。原库、b15克隆、旧测试卷不写。
   - 当前18表仅全局 Capability目录有10行，租户表均空。若需证明 RLS 正反链，只在此新克隆 `aip_budget_head` 写入一个唯一标记的 `org-org/dev-project` **test-only** 行（该表六列、仅主键/check且无用户触发器已只读核），独立 Reader 正向1/错租户0；随后只删除这一新造标记行，再复核源/克隆26表数据摘要等形。绝不写 `dev-org` 或把合成行冒充正式业务配置。
3. 该克隆 `--network none` 且本地 trust 初始化，仅验证真实 PostgreSQL session/RLS/ACL；**不把它当私有密码认证或正式 API 接线**。b3 已单独证私有 passfile连接；正式 Reader/issuer 仍需当前可核凭据、外部 OIDC、零执行窗口。测试后 Reader role/policy 可留在新 test-only 克隆作为验收状态，但不得接当前 API；记录不可逆操作及精确状态。
4. 无生产代码改动则专项为真实 PG 事务/独立登录与原库只读回读，不重复跑无变化单测或浏览器。方案/逻辑一致性复审、verification、m1 精确提交、AOS/Prime/D-waves 同步，继续独立主线。

边界：当前真实库只读，Host/worker/Provider关，`org-org/dev-project` 唯一正向、`dev-org` 零副作用，不读商城源、不回放旧12 Run、不手工 Run、不碰230 L0、不 push。
