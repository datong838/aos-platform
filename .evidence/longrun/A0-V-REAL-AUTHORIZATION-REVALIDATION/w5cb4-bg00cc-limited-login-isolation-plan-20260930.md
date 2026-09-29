# W5CB4 BG00cc｜受限 DB 登录与网络批准签发边界隔离方案

## 依据和范围

按 AGENTS.md、AOS 工程交付 Rules，复习 231/231-5、41、BG00ca/cb。BG00cb 证明当前预览 API 的 `aos_app` 是超级用户，`aos_runtime` 可直接写 ApprovalEvent；网络 active 的 a0v116 DB 门仍关。本波先验证现有独立 NOINHERIT 运行登录在显式 test-only 全库克隆中的可用边界，再确定最小改动。正租户当前库只读；不采集/输出密码，不读商城源，不启动 Host/worker/Provider。

## 文件级计划

1. 读 `scripts/a0v_ecommerce_runtime_host.py` 的凭据文件校验和 `services/aos-api/aos_api/db.py`、`tenant_scope.py` 连接/事务规则；从本机 mode600 的既有凭据读取 runtime DSN，仅内存替换 dbname 为 `aos_bg00bx_cutover_testonly_20260930`，不打印 DSN/密码。
2. 在 clone 上 READ ONLY 事务以受限 login → `SET LOCAL ROLE aos_runtime`、精确 `org-org/dev-project` GUC，核当前安装/Network Proposal/ApprovalEvent/Network head 的 SELECT 权限；另核 login 是否可不经设角色直接访问与能否自行重置角色；禁止对 clone 写业务事实。
3. 对照网络专用 OIDC Router、Store 的 Event INSERT、Event 表 ACL/触发器和受限登录边界，记录是否存在仅靠角色/SECURITY DEFINER/GUC 就能证明 OIDC 签发的路径。若仍无，保持 active 禁入，下一波提出目标明确的签发凭据/事务改造，不引入自设放行标记。
4. 仅新增本波 plan/verification、续接 356、D-waves；无应用/迁移代码时不虚构 RED/GREEN。检查相邻正式代码未改，精确提交 m1，authority CAS 更新 01/06 与 Prime。

## 判据/风险

记录数据库与卷身份、角色/ACL 查询、只读事务退出码、当前 PG Proposal/Event=0 及 a0v116 active trigger 有效；证明受限登录可用只算隔离连接证据，不等于正式签发。当前 API 登录切换和 Event DB 门是独立后续施工；当前实例迁移需新备份、第二全库克隆、零执行窗口。第二正式 checker、八配置、自然首链仍缺。
