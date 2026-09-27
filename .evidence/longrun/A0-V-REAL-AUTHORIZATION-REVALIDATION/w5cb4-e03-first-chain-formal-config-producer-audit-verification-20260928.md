# W5CB4 E03：首链正式配置生产者审计验收（2026-09-28）

## 结论与证据

本波为只读审计。m1 基线 `048d6cfc`；8080 OpenAPI 与 8434 工作台均 HTTP 200，18181 无监听。当前卷已按 E02 证据升为 `a0v_107`，本波未读商城源库、未发业务 POST、未启动 Host/worker/Provider。

当前 `org-org/dev-project` 权威计数（只读查询）：`aip_logic_graph_revision=0`、`aip_logic_publication=0`、`aip_release_gate_decision=0`、`aip_publication_event=0`、`aip_model_route_revision=0`、`aip_runtime_policy_revision=0`、`aip_skill_binding=0`；Provider、registered model、budget revision、capability binding 均为 0。六个 AgentInstance 仅说明数字身份存在，不证明其可执行。D01 的 MethodRevision、MetricDefinition、AnalystQueryResult、EvidenceBundle、EvalContract 亦为 0。

`LogicCanvasPage.tsx` 已有 Logic Graph 的正式操作入口，但签名包 `content/logic/ecommerce-37-logic-catalog.json` 仅有 lifecycle/readiness/blocker 描述，没有可执行 Graph；其 `logic_revision_unavailable`/`eval_pack_unavailable`/`aip7_route_authority_unavailable` 不能靠复制目录消除。`ecommerce-analyst-query-templates.json` 指向旧 bundle 1.3.0，当前签名包 1.11.0，不能冒充当前 exact 模板。模型路由没有真实 Provider/模型/预算，禁止伪造健康和费用。Skill 发布页三组候选为空、按钮被禁用，与此一致。

`ecommerce_analyst_authority_store.py` 已有 `publish_method/get_method_exact`：tenant 限定、actor=createdBy、内容哈希、advisory lock、版本 CAS、幂等 Receipt 和 exact 读回；`MethodRevision` 只允许 `descriptive_snapshot_v1`/`observation`，明确不是因果批准。路由与工作台未暴露该 Owner。这是目前可独立实现、无需外部 Provider 或虚构业务批准的最小正式来源生产者。它不会直接证明 D01 数据、Logic 发布或首链完成。

## 下一波 E04 文件门与退出

先补 E04 方案，再做 `services/aos-api/aos_api/routers/` 下的受限 MethodRevision 创建/精确读回路由、路由装配及邻接测试；`apps/web` 仅增加经营参谋现有工作台内的明确编辑/读回入口，不建第九菜单。任何 POST 必须有固定幂等键、未知结果冻结、租户与角色校验，不能经离线队列重发。专项、累计、浏览器只读/受控最小正例、方案一致性、证据与上下文更新之后再自动进入下一波（Metric/Evidence 等依真实缺口择一）。如产品入口需新身份权威或权限模型，先收缩方案，不做宽松假入口。

E03 完成仅证明“下一可开发切片已选定”；不证明真实方法已发布，也不改变 BG-00～04 的验收状态。旧 12 Run 继续保持冻结，不重放、不删数据。
