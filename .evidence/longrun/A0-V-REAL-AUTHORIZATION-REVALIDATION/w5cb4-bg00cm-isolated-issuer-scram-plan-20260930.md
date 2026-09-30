# W5CB4 BG00cm｜隔离克隆 issuer SCRAM/HBA 真实登录方案

## 依据和快照

接 AOS-000942，复习 231-4 非 owner/角色/事务门、231-5 人类审批与幂等、BG00cj 数据库触发器和 BG00cl HBA 禁入。新独立 PG16 克隆 `aos-bg00ck-isolated-pg` 位于 `colima-aos-a0v-test-only`、独立卷 `aos-bg00ck-isolated-pg-data`、127.0.0.1:18437，库 `aos_current_preview_20260927@a0v_118`。当前 issuer NOLOGIN、NOINHERIT，只是 `aos_runtime` 成员，不是 owner 成员，且当前库 CONNECT=false。克隆 HBA 有通用 local/127/::1 trust；当前权威卷保持只读，Host/worker/Provider关闭。

## 文件级和实例级顺序

1. 在私有0700目录保存克隆 HBA 原文、SHA256、角色/授权基线，不输出密码。只改这个独立克隆：在现有宽泛 trust 前插入三条目标数据库＋issuer 用户的 socket、IPv4/IPv6 精确 SCRAM 规则；`pg_ctl reload` 后 `pg_hba_file_rules` 无错误，BG00cl gate 必须 GREEN。任何不确定先回滚克隆配置并停。
2. 仅在克隆随机生成私有0600 `PGPASSFILE`，`ALTER ROLE issuer LOGIN PASSWORD` 与数据库精确 CONNECT；确认 `rolsuper=false`、NOINHERIT、非 owner、只属 `aos_runtime`。错密码、普通 runtime 网络 Event、owner/角色切换等负例拒绝。经宿主127.0.0.1:18437真实 TCP 正确密码登录，`session_user=issuer`；事务内 `SET LOCAL ROLE aos_runtime`、精确 tenant GUC 后 Event/状态更新并 `ROLLBACK`，回读 Event 0、Proposal仍drafted。由于 maker seed 与 issuer 在两个独立连接，测试专用 Proposal 需在克隆先提交一条，持久残留明确记录且不得回流当前库；不能用 superuser `SET SESSION AUTHORIZATION` 当正例。
3. `services/aos-api/tests/aip/` 新增隔离专项。测试必须指向显式白名单克隆，`AOS_TEST_USE_SHARED_DATABASE=1`，先 RED 再实现；不得让测试自动创建/删除库。若现有通用 store 的角色权限不足，仅定位最小缺口，不扩大所有 Action 的授权。
4. 验证落盘、方案/代码复审、精确提交与上下文同步。此波只证明克隆的数据库身份链，不接生产 issuer 凭据或 API 进程，不给当前真实库启 LOGIN。下一波才设计独立签发进程与外部 OIDC/第二 checker 的合法连接。

## 止损

仅操作 `colima-aos-a0v-test-only/aos-bg00ck-isolated-pg`；不读商城源，不写 dev-org，不运行/回放旧 Run，不手工 run_definition，不删除库/卷/备份、不 push。测试期间任何真实外部业务副作用为零。当前实例 HBA trust/issuer NOLOGIN 保持禁入。
