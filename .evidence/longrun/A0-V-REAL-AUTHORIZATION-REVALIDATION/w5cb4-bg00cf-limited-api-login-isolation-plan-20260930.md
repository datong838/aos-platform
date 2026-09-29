# W5CB4 BG00cf｜当前 API 受限登录隔离兼容与网络 Event 信任边界方案

## 依据与当前门

复习 AGENTS.md、aos-engineering-delivery、231/231-5 人工审批/安装/租户边界、41 NetworkPolicy/Egress exact 合同及 BG00cb～ce。当前 AOS-000934、代码 m1 `eaf4459a`、权威卷 `aos-a0v-recovery-pg-data` 的当前库 `a0v_117`，签名安装 approved1、published4、binding0；Host/worker/Provider及18181关闭。当前 8080 `a0v_current_preview_http.py` 的签名预检只读，但 `--serve` 使用容器 `aos_app` SUPERUSER/BYPASSRLS 登录。BG00cc 已证现有 runtime NOINHERIT 身份需 `SET ROLE aos_runtime` 才能读表，却仍可直写 ApprovalEvent；BG00ce 已轮换其明文泄露密码。

## 本波文件级工作

1. 读 `scripts/a0v_current_preview_http.py`、`services/aos-api/aos_api/db.py`、`tenant_scope.py`、`main.py` 生命周期与专用网络 Router/Store，核哪些读/写事务依赖 owner。只读核当前 signed receipt/PG身份及服务；不改当前 DB/角色/服务。
2. 重启 BG00ce **独立** `colima-aos-a0v-test-only` PG16 集群（127.0.0.1:18436，完整 a0v117 恢复本）。仅在此独立集群创建新的 test-only `NOINHERIT LOGIN` API 角色，授予当前克隆 DB CONNECT 与 `aos_runtime` 成员资格；随机假密码存离仓0600文件，不写命令参数或环境。用 `PGPASSFILE` 路径和无密码 `AOS_DATABASE_URL` 测 `db.connect(TenantScope('org-org','dev-project'))` 与 `connect_platform()`，读现有安装/Proposal/Network控制表，不读商城源；登录自身直读、跨租户与 owner 冒充应拒绝。
3. 按 `a0v_current_preview_http.FLAGS` 关闭一切 worker/Host/Provider，在独立克隆上以 test-only 受限身份运行 API 生命周期和本地 `/openapi.json`/必要只读路由。任何启动 DDL/权限失败原样记录精确调用点；不使用开发账号、手工 Run 或 test-only 结果冒充正式 OIDC/业务首链。
4. 对照 `decide_network_activation` → `AipActionStore.decide` → ApprovalEvent 的事务，形成最小签发边界：普通 API 登录无 Event 网络直写、专用发行身份不能由普通登录 `SET ROLE`、OIDC 主体及 exact Proposal/撤销必须同事务受控；目前只设计和隔离负例，不在当前库放开 active。
5. verification、续接 359、D-waves，必要时最小 test-only 工具/测试代码按 RED→GREEN；专项/相邻回归、方案复审、精确 m1 提交、authority CAS/Prime 回读。

## 停线/判据

`aos_app` 超级用户现状、未满足权限或启动失败不允许悄然回退高权路径；记录差异并转后波修复。API受限登录只证明数据库身份边界，Event普通 runtime 仍有 INSERT/UPDATE、正式第二 checker与八配置仍缺，a0v116 active触发器和 Host禁入必须保持。当前真实库只读；任何正式角色/连接切换另波需新一致备份、独立克隆回归、零执行窗口。保护无关 dirty 文件，不 push。
