# W5CB4 E17-s3o-w-f｜职责 Plan 创建 operation 白名单验证

基线：`aos-platform/m1@c6a63e9f`，Authority `AOS-001214`，2026-10-03。先复习 231-3/4/5/9、栖月汇方案及本波 plan；文件级范围仅 `aip_production_contract_store.py` 的 create in-transaction operation 入口和 `test_w2b_production_contract_store.py` 的三个负例。修复前真实隔离 PG 负例先落到 `RESPONSIBILITY_TEMPLATE_AUTHORITY_UNAVAILABLE`，证明非法 operation 越过入口，**不证明**已伪造 Receipt；修复后入口在依赖读取和 SQL 前以 `ProductionContractConflict("unsupported Plan creation operation")` 精确拒绝，Plan head 零增量。原 generic/BI operation 保持允许。

| 检查 | 命令/结果 |
|---|---|
| 专项 | `pytest -q services/aos-api/tests/test_w2b_production_contract_store.py -k unsupported_plan_creation_operation`，3 passed，exit0。 |
| 相邻 | `pytest -q services/aos-api/tests/test_w2b_production_contract_store.py services/aos-api/tests/test_ecommerce_business_investigation_aip_authority.py`，55 passed，exit0。另一个 Growth 签名安装全 schema 测试因要求 `AOS_EXTENSION_OCI_TEST=1` 和本地正式签名 Growth receipt 而 skipped，不计通过。 |
| 静态/差异 | `compileall` 和 `git diff --check` exit0；精确代码提交 `c6a63e9f`。方案与代码一致：只增加 create 入口两种 operation 白名单，未修改 revise/freeze、Receipt schema、CAS、迁移或原 API 接口。 |
| 最新代码/权威卷 | 代码 HEAD `c6a63e9f`、`m1`；代码 migration 与库均 `a0v_135`。`aos-a0v-recovery-pg` 仍挂 `aos-a0v-recovery-pg-data:/var/lib/postgresql/data`；`aos_current_preview_20260927` 只读回读 `a0v_135`。独立全备 `aos-recovery/.aos-current-backup-20261003-post-reboot-135/current-full.dump` SHA256 `e2c3a4b6881e5b4616b92ce42052227d6a20fa34b4310debcda83c939c9e04a0`，TOC 5905 行；本波没有全库恢复演练。签名预检 `a0v_current_preview_http.py --signed-receipt .../.aos-current-build-pyGkqQ/signing-receipt.json` exit0，approved 安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813`、publishedVersions4、runtimeBindings0。 |
| 完整重启 | 原 Web/API launchd `bootout` 均 exit0，8080/8434/18181 均无监听；`docker --context colima-aos-extension restart aos-a0v-recovery-pg` exit0，PG StartedAt `2026-10-03T04:28:29.35891475Z`；PG `pg_isready`、签名预检 exit0；原 API/Web plist 顺序 `bootstrap` 均 exit0。新 API PID65103、Web PID65156；18435/8080/8434 LISTEN，18181 无监听。API 日志 `2026-10-03T04:29:02.129619+00:00 startup_extension_runtime_host_inactive code=DISABLED`。 |
| HTTP/浏览器 | `/v1/health`、`/v1/ready` 各200，八个 `/workshop/*` 页与 `/aip/skill-publish`、`/aip/agent-catalog` 均200。首轮 shell 循环变量误名 `path` 遮蔽 PATH，`curl` exit127；改变量名 `route` 后全量复验 exit0。Codex 浏览器 CUA 重新加载用户已有 `/aip/skill-publish`，截图及 AX 留当轮工具证据：`org-org/dev-project`，37 已评测、0 已发布，三项发布阻断且按钮 disabled，导航无业务工作台入口。 |
| 业务禁入只读回读 | `docker exec ... psql -U aos_app -d aos_current_preview_20260927` 在 `BEGIN READ ONLY` 下运行原 `read_candidates` SQL，八类计数 `0|0|0|0|0|0|0|0`，exit0。绑定/Host assignment/全表 Host identity 计数均0，exit0。第一次按租户列查询 identity 表失败：该表无 `org_id`，exit1；改为查全表后 exit0。 |

结论：电脑重启后当前预览栈已按最新提交和原权威卷完整恢复，入口越权 operation 被应用层失败关闭，浏览器禁入仍在。**不是**正式发行者数据库 ACL 修复、Growth1.13 发布、配置/身份授权、安装绑定或经营首链验收。`s3o-w-e` 的临时触发器仅覆盖 Plan/Content 部分 operation；共享 Receipt 还有其它写者。下一波应先盘点全部原写者与 operation，在原表形状、受限连接的隔离克隆验证合法路径后，单独制定正式 issuer/ACL 迁移与当前库安全切换方案。当前权威库只读，Host/worker/Provider 关闭；未读商城源、重放旧12 Run、手工 run_definition、写 dev-org、删除库/卷/备份或 push。
