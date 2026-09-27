# W5CB4 E09：首条管道正式登记验收（2026-09-28）

## 结论

承接方案 `4eb4c1f4`、实现 `f4e5520b`。现有 Data OS `meta_source`/`meta_pipeline`/`meta_dataset` 仍是唯一配置 Owner；新增 `a0v_109` tenant-scoped 不可变 `pipeline_registration_receipt`。正式产品入口只对当前已登记来源的配置修订登记首条管道、输出数据集及原命令回执，同一数据库事务提交。同 key 同请求只返回原公开结果，异请求冲突；未知响应仅以原 key GET 回执，前端 pending 冻结且不自动重发。旧 `/v1/pipelines` 保持兼容，不在新入口使用其分步持久化。登记不连接来源、不执行同步、不启动 Host/worker/旧 Run，也不代表 SourceSelection 或业务结果已获批。

## 验收

- `apps/web` TypeScript `--noEmit`、Vite 生产构建通过；前端专项 2/2，累计 306 文件、2685/2685 测试通过。后端登记、来源回执与精确路由封印累计 18 passed、2 subtests；路由 4522、OpenAPI paths 2717、摘要 `b68fcd1fd8b0b8d6e1c12ff24de7191432b0abe867e0d5bf6ef851f52264720c`，既有重复集合不变。
- 当前卷 `aos-a0v-recovery-pg-data` 的 `aos_current_preview_20260927` 在升级前为 `a0v_108`、源/管道/数据集 0。完整 custom-format 归档位于 `/Users/ddt/work/projects/ai_agent/.aos-e09-current-backup-6x8SFb/aos_current_preview_20260927_a0v108_with_acl.dump`，权限 0600、SHA-256 `21db7bf48c5eb38fc3457a5b1f121dd64634da921a955bed2adcf6a4635c377f`，`pg_restore --list` 可读；独立恢复到 `aos_e09_pipeline_acl_20260928` 并升级 `a0v_109`。先前不含 ACL 的辅助归档和隔离库也保留，但不作为运行角色验收依据。
- 在含 ACL 的隔离库，仅创建合成 file 来源，实测原 key 重读、不同 payload/key 冲突、跨租户回执不可见；最终 `meta_pipeline=1`、`meta_dataset=1`、`pipeline_registration_receipt=1`。这是隔离测试，不是当前业务库的真实商品/订单数据。
- 现有 API/Web 精确进程停用后，原命名卷仅增量迁移 `a0v_108→a0v_109`，数据库容器原地重启，未重建、清理或删除卷。当前回读：安装 1、发布包 4、运行绑定 0、源 0、管道 0、登记回执 0；signed profile 预检 GREEN、安装 approved、迁移 disabled、Host/worker 0。最新代码 API 8080 `/v1/health` 与 Web 8434 `/data/pipelines` HTTP 200，新回执 GET 匿名 401；18181 未监听。
- 浏览器管道页显示 `0/0`、正式登记面板只提示无来源并链接数据源管理；数据源页显示来源 0、近 24 小时同步 0。未在当前业务库提交合成来源或管道，也未调用 `/test`、`/syncs`、构建或商城源。浏览器侧栏工作台目录曾显示“读取失败”，此信号单列待查，不据此宣称八工作台端到端通过。
- `git diff --check` 通过；自动出现的无关锁文件漂移已恢复，保留原有不相关脏文件。本波仅精确提交方案、代码、专项测试与路由封印。

## 方案一致性、剩余风险与下一波

方案的最小文件级边界、只读对账、单写者、租户隔离和无越权副作用均保持。隔离库验证了正向提交及三行数量；尚未以真实授权源和正式操作者在当前实例提交第一条管道，因此不能声称首条业务链已自然运行。已有 `meta_dataset` 的 12 个遗留可见条目属于列表投影，不能据此推断当前正式来源存在。旧 12 Run 仍冻结，不以 E09 替代正式退休手续。

下一波 E10：先复习 231/231-9 及产品方案，细化 SourceSelection/运行配置的产品准入生产者，优先让当前安装能在不手工接线下形成可审查配置；继续独立测试和安全空态验收。每天用当日最新代码及当前命名卷重启数据库/API/Web，并读回版本、安装、端口、页面和核心状态，然后立即进入下一安全波次。
