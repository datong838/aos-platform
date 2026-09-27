# W5CB4 E08：SourceSelection 原命令回执验收（2026-09-28）

## 结论与边界

承接 E08 方案 `44ecc966`、实现 `fa9d6b5c`。现有 SourceSelection Owner 的正式审批行本来已保存原幂等键、请求摘要和 exact ref；本波只增加 `GET /v1/pipelines/{pipeline_id}/source-selection-approvals/receipt`，由当前 principal 及独立 runtime worker 身份读取与原 actor、租户、安装、generation、pipeline、key 全部一致的原审批引用。保存行经既有解码/内容 hash 校验；缺失 404，权限错 403，身份/DB 不可判定 503。回执只证明原审批命令结果，不证明当前安装/窗口仍有执行权；不调用 `append`、源库、运行 worker 或 `run_definition`。未在当前业务库制造任何源或审批行。

## 验收证据

- 独立无持久卷临时 PG 上，Owner PG、HTTP、服务、存储、路由封印组合回归：85 passed、2 subtests；随后增补服务层 fence 断言和 OpenAPI 原键头声明后，HTTP/服务/封印再跑：56 passed、2 subtests。临时测试容器停止并自动清理；当前权威卷未用于该写测试。
- 原 actor/key 精确读取同一 ref；错安装、代次、pipeline、actor、key 均不得读到；错租户角色拒绝；回读前后审批行数不变，审批回调只发生一次。匿名 HTTP 回读 401；无键/无效查询与服务异常有明确拒绝且不自动重试。路由总数 4520、OpenAPI paths 2715、摘要 `5b0f3f026858087116a02212002cdcaa83d11201ebf55e3e87153206eaf04751`，既有重复路由集合未扩大。
- 最新代码重新启动 API；当前 `aos-a0v-recovery-pg-data` 命名卷中的 DB `aos_current_preview_20260927` 是 `a0v_108`，preflight GREEN，安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813` 仍 approved，发布包 4、运行绑定 0。只读 DB 回读 `meta_source=0`、`meta_pipeline=0`、`pipeline_source_selection_revision=0`、`extension_runtime_binding=0`。8080 `/v1/health`、8434 `/data` HTTP 200，新增 GET 匿名 401，18181 未监听；迁移 disabled、Host/worker 0。Web 进程亦为新进程。浏览器重载后资产 Registry 显示 4 包、数据源页显示 0 源/同步 0。API 刚启时页曾短暂显示读取失败，重载后权威读回恢复，不将短暂 200 当业务成功。
- `git diff --check` 通过；未修改、删除历史业务卷或用户其他工作树变更。

## 方案/代码一致性、未关门与下一波

复核 231/231-9 BG-00→BG-01/02：回执读口保持单一 SourceSelection 权威，没有另造审批表，也没有把精确引用当可执行令牌。当前预览 profile 没有独立 runtime worker 凭证；有身份的真实 GET 在此 profile 会 fail closed，不可为得到 404 而降权到 Web/超管连接。本波 HTTP 契约与独立 PG 证明代码路径，但**不证明当前实例能提交审批、自然触发、商品新鲜或八场景闭环**。

E09 优先审查并补当前安装/运行配置与正式源/管道的产品准入最小生产者；若尚缺真实源授权，继续可独立开发的下游配置/恢复，不把补旧 12 Run 或旧快照每一行当主线。每天最新代码+当前命名卷全栈重启核验后自动继续 Loop。
