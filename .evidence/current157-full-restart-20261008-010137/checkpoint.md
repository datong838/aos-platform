# 最新已提交 m1 原卷完整重启验收

提醒 event 2026-10-08T01:01:37.490Z。本轮部署源是 m1@8658a3fcb75d280eb454bc342629af8a9fb72c80 的逐文件 Git blob 核验冻结副本；未部署工作树中的158。当前库与该提交代码迁移头均157，无迁移。

原容器9cc6091c…、原卷 aos-a0v-recovery-pg-data、原库 aos_current_preview_20260927 保持；PG实际新启动2026-10-08T01:10:23.54830361Z；API26897启动09:10:26；Web27312/helper27313启动09:12:12（Asia/Shanghai）。新API/Web均使用本轮冻结源，8080/8434唯一listener，身份、启动时间与cwd独立回读一致。原签名Receipt预检GREEN，批准安装ccdcb0f0-1040-4bc6-aa0c-d045f5689813、publishedVersions4、runtimeBindings0。

Web首启因冻结目录缺少app层已有vitest依赖退出，已先对账再仅补链接原已安装 apps/web/node_modules；没有重放PG/API重启，没有依赖安装、产品代码或锁文件修改。原失败与r2操作记录均保留。

真实浏览器八路逐页显示当前入口不可用；驾驶舱只读目录重读仍拒绝。组织org-org/工作区dev-project实际选中，应用列表有效入口0。API两个目录正向200，dev-org两个目录403 AUTH_TENANT_UNKNOWN。浏览器2/tab1保留于/workshop。此为本机禁入预览验收，不是自然首链。

浏览器后独立 SERIALIZABLE READ ONLY 对比615张全部用户schema表count/hash及public catalog均与重启前一致。无Host/worker/Provider、商城源读取、旧Run、手工run_definition、push或Goal状态操作。当前Goal回读仍blocked，现有受支持恢复能力缺口不改变安全施工接续；不改私有存储。

完整维护门已通过；随即继续gt-model-typed-proof-20261008逐case签名/义务/Report协议研究。完整Model可信证明与正式首链仍pending。只提交本目录精确验收证据，不提交Model未收口代码与其他dirty。
