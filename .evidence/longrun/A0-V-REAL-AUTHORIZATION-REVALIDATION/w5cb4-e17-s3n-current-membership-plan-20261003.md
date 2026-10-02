# E17-s3n AssigneeResolutionReceipt 当前成员资格：文件级方案

基线 `aos-platform/m1@14d0fc12`、Authority `AOS-001184`，Task `W5CB4-E17-S3N-ASSIGNEE-RESOLUTION-CURRENT-MEMBERSHIP-20261003`。先读 231/231-9、49-W6-01、115 工作台 exact subject 合同、原 `AipAssigneeResolutionStore.resolve`、Plan create/freeze 两段依赖读取与 Analyst Stage Review 的当前成员检查。真实库 `a0v_135` 只读，Host/worker/Provider关闭。

## 定位

原 resolver 对 `human_principal` 要求 `meta_membership(org_id,project_id,subject)` 存在，再写不超过 freshness 的 immutable Receipt。Plan `_require_exact_assignee_resolution` 当前确认 Receipt subject/状态/期限/assignee/capability，却不重读成员资格。已有 Analyst Stage Review 在执行前另行查成员，说明运行时禁入存在，但 Plan 在成员撤销后、Receipt 未到期时可能仍创建或冻结为 READY。49 ADR 要求 drift 使 Stage blocked，231-9 要求退出撤销任务分配与访问。

1. 在 `services/aos-api/tests/test_ecommerce_analyst_stage_review_authority.py` 复用 `disposable_database()`，org-org/dev-project 先以原 resolver 出有效 human Receipt 和 draft Plan，再在同隔离库删除该成员；分别检 Plan 读取 readiness 与 freeze 是否拒绝、freeze Receipt0/head不动。旧码先跑 RED，确认问题。对同一成员状态下正向继续通过；不在只允许 org-org 的夹具里假造 dev-org。
2. 若 RED 且其他使用者合同不冲突，只在 `services/aos-api/aos_api/aip_production_contract_store.py:_require_exact_assignee_resolution` 的 HUMAN_PRINCIPAL 分支同租户事务重读 `meta_membership`；不存在时以 `ASSIGNEE_RESOLUTION_MEMBERSHIP_REVOKED:<slot_id>` 失败关闭。此共用方法也用于只读 Plan 查询，不能无差别加 `FOR SHARE`；原 Stage Review 执行门已另持成员行锁。Plan 检查与并发撤销之间的极短竞态列剩余风险，后续若要交易级封闭须区分读写调用者再设计。保留 Receipt 历史、不改 resolver/迁移、其他三 kind 不碰。对 draft/readiness 的 blocker 走原 `ASSIGNEE_RESOLUTION_INVALID` 包装。
3. 跑新负例、原 Analyst 正向、W2B/Resolver/内容评审相邻串行回归，明确记录旧 RETURN 测试的既有合同冲突；py_compile、diff check、方案/代码复审。必要时原浏览器只读看仍禁入；真库不触发 Plan/Run。

相邻原 Analyst 测试曾要求在成员删除后由 Stage Review 返回 `tenant member` 文案；新共用 Plan 门会更早把原 frozen Plan 判为 stale/drifted。只调整该测试的期望文案为原服务对失效 Plan 的拒绝，并加 Plan readiness/blocker 核对；禁止弱化为“抛任意异常即通过”。

剩余：Human 角色/ABAC/值班容量当前性与机器 Binding 失效不是此最小分支的完成声明；DB 角色直写 Receipt/Binding 是独立 issuer/ACL 迁移波。首链仍按正式身份、八配置与 Host Owner 分门判定。
