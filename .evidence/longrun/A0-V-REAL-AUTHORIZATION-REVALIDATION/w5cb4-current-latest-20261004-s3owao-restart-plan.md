# 2026-10-04｜s3o-w-ao 新代码与权威卷完整重启方案

- 基线 `aos-platform/m1@b409ac51`，唯一代码 migration head=`a0v_135`，当前容器 `colima-aos-extension/aos-a0v-recovery-pg` 挂 `aos-a0v-recovery-pg-data`、库 `aos_current_preview_20260927@a0v_135`。签名预检原 receipt `.../.aos-current-build-pyGkqQ/signing-receipt.json` exit0：approved安装、4已发布版本、runtimeBindings0。Host/worker/Provider保持关，18181不监听；本波只重启 PG/API/Web，不迁移或写当前业务数据。
- 重启前用新独立0700目录 `/Users/ddt/work/projects/ai_agent/aos-recovery/.aos-current-backup-20261004-s3owao` 保存0600全备、SHA256与 `pg_restore -l` TOC；若失败不停止现有服务。前波同一卷 `a0v_135` 备份已在独立 clone 完整恢复且摘要相同；新备份仍须单独校验，不能把 TOC 当成新备份的全库恢复演练。
- 核 launchd 原服务 `com.aos.a0v-api-daily0900` 和 `com.aos.a0v-web-8434` 的程序路径、原代码树、签名 receipt、Web proxy；先 bootout Web/API 并断言8080/8434/18181关闭，再 restart **原** PG 容器，不造新卷。PG ready 后只读核库名/版本/安装，再 bootstrap 原 API/Web plist；核新 PID/启动时间、健康/就绪/OpenAPI/八工作台、页面和浏览器失败封闭；API readiness 默认无正式 Reader 应拒绝而不调用 owner。任何异常保留现场、只读诊断，不重发业务命令。
- 源库角色/配置仍缺：不启用 Runtime Host、自然 worker、Provider，不读商城源、不重放旧12 Run、不手工 `run_definition`、不碰230 L0、不 push。重启成功仅证明最新禁入预览栈，不证明首条经营闭环。
