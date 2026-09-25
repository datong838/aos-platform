# W5c8q｜专用见证写主体与原输入绑定函数（隔离 PG）

## 基线与停线

承接 W5c8p `m1@09ab7c06`/AOS-000678 的权限审计。真实库未迁 a0v_096/097、真实 profile 停止；本波可以把**未授权给任何应用身份**的角色/函数结构加入下一 migration，并在一次性隔离 PG 验证，不触碰真实库、不接 Worker/ACK。函数存在不代表真实回填或 Host/Delivery 授权。

## 文件级任务

1. 新增 `services/aos-api/alembic/versions/a0v_098_snapshot_group_witness_backfill_gate.py`，down_revision `a0v_097`。独立 `aos_snapshot_witness_backfill` NOLOGIN/NOSUPERUSER/NOBYPASSRLS/NOINHERIT/NOCREATEDB/NOCREATEROLE/NOREPLICATION，无运行角色成员关系；如同名角色属性不匹配即迁移失败。仅授原 claim/input/member SELECT 和 sidecar INSERT/SELECT 给专用角色。新增固定 search_path 的精确函数，拥有者为专用角色，禁止 PUBLIC/runtime/directory/maintainer EXECUTE；不得将角色授予应用登录身份。
2. 函数输入精确 `(org_id,project_id,group_id,binding_canonical_json,manifest_canonical_json)`，返回仅 `INSERTED`/`ALREADY_PRESENT`。调用时必须精确专用角色、租户 GUC 匹配、非 superuser/bypassrls 的 session_user 且已拥有该角色的显式成员关系；由于**当前没有授权的应用登录身份**，正常环境仍不可调用。隔离 PG 用临时无超权测试登录主体验证。函数内部锁定不可变原 claim/input、核对原双 hash、canonical 文本 UTF8 sha256、JSONB 等值、member_count/ordinal/runId；失败即 SQL 异常，不插 sidecar。唯一键处理同值重入与异值冲突，但上位 unknown 禁止外部自动重试。
3. 新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c8q_witness_backfill_gate_pg.py`：先 RED 函数/角色缺失；隔离 PG 正例与缺 input、错租户、hash/JSONB 漂移、成员漂移、重复异值、运行角色无权限；若临时测试登录身份或角色无法安全收回，改为角色权限静态验证，不能声称执行身份 GREEN。
4. 不改原表、W5c8n 报告、Worker、Outbox、Host 或 ACK。不运行真实扫描/迁移；不读商城源。

## 九步

1. 复习上位产品/技术、W5c8p 审计和当前 m1/测试 profile。
2. 方案落盘提交，接口/角色锁定。
3. 隔离 PG RED 失败用例。
4. 最小 migration GREEN，不授应用 EXECUTE。
5. 专项、累计、权限矩阵、测试库 0/静态检查。
6. 无业务 UI 则浏览器不可验收，记录本机只读状态。
7. 方案/代码权限、并发、哈希、自洽复审。
8. verification、m1 提交，D-waves/AOS CAS/Prime。
9. 自动 W5c8r：独立部署前只读门与授权主体路径；真实迁移、扫描、回填、ACK 另立顺序门。

若角色/权限闭环、原值绑定或完整 PG 负例不能成立，STOP、记证据、不扩大授权。230 L0 挂起；dev-org 零 canary；unknown 不重发/不手工 `run_definition`；m1 单写不 push。

## RED 后权限拆分订正

`m1@47515df6` 原稿的单角色方案会让未来被授予角色成员资格的调用者也获得侧表直接 INSERT，不能实施。改为两个无登录角色：`aos_snapshot_witness_backfill` 仅作函数 owner，持原表 SELECT/sidecar SELECT+INSERT，**永不授成员给应用/调用者**；`aos_snapshot_witness_operator` 仅持函数 EXECUTE，绝无侧表 INSERT。两者都 NOLOGIN/NOBYPASSRLS/NOINHERIT，迁移验证属性与无成员。函数为 SECURITY DEFINER，固定 search_path，要求 session_user 为无超权的显式 operator 成员且当前 SET ROLE operator、精确租户 GUC；默认无任何现有应用登录身份是 operator 成员。隔离测试可创建临时无登录 caller，测试后精确撤销并删除该 caller。若无法证明无表权泄漏，STOP。
