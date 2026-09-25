# W5c8q｜专用见证写主体与原输入绑定门隔离验证

## 方案/范围

承接 W5c8p/AOS-000678；方案 `m1@47515df6`，RED 后补订**函数 owner 与 operator 双 NOLOGIN 角色**，避免给调用者侧表直接 INSERT。新增 `a0v_098` migration 与隔离 PG 测试；没有真实迁移、历史扫描、Worker 接线或 ACK。

## RED/GREEN 与复审

- RED：角色缺失，专项 `1 failed`，失败点 `role is None`；随后实现 migration。
- 角色/函数轻量 GREEN `1 passed`；完整隔离 PG 初版 `2 passed in 118.89s`，补强直接 INSERT、缺 input、同 JSONB 不同文本 hash 与双连接同键竞争后最终 `2 passed, 7 warnings in 117.95s`。
- 原 12-member 完整保存组的 canonical 文本经非超权临时 caller（仅 operator 成员、显式 `SET ROLE`）进入函数；operator 直接 INSERT sidecar 被数据库拒绝；函数精确同事务核对原 claim/input/member、双 hash 与 JSONB 等值。成功后同值再读 `ALREADY_PRESENT`，坏 manifest、仅加空格的 binding、缺 input 组与错租户均拒绝。两个 RR 连接竞争同键，只能有一个 `INSERTED`，另一方限于已存在或序列化拒绝；不对未知外部结果做自动重试。
- 运行角色、directory、maintainer 无表 INSERT/函数 EXECUTE；函数 owner 是独立 backfill 角色，operator 无直接表 INSERT。migration 对双角色属性及当前成员关系 fail-closed；没有授予任何现有应用登录身份 operator 成员资格。
- 相关累计 82 passed；Python 编译与 `git diff --check` 通过。隔离 `aos_test_*` 数据库残留 0、临时 `aos_test_witness_*` caller 角色残留 0。
- 本波无业务 UI；`8080/docs` HTTP 200 仅证明本机开发文档可达。真实 `aos-extension` profile 停止、测试专用 profile 运行；业务浏览器/真实租户未验收。

## 仍冻结的门

- 真实库未迁 a0v_096/097/098；部署角色成员资格和真实 RLS/owner 差异未读回。原 12 Run 当前结果、Store/Delivery Receipt、Host fence 未读回；本波不能启动 writer、回填、ACK 或 closure。
- 未对真实历史批量数值歧义、跨 Host/长事务、损坏但可提交的 member/input 或真实租户规模做证明；完整 SQL 拒绝矩阵继续后继波。新函数不接任何应用路径，内部 `ALREADY_PRESENT` 不改变上位 unknown 不重发规则。
- W5c8r 先独立只读部署前审计与剩余 PG 拒绝矩阵，未有明确全链证据前不迁真实库、不授权 operator 给应用。

230 L0 挂起、商城源不读、dev-org 零 canary、m1 单写不 push、不动其他分支。
