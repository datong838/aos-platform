# E17-s3o-b｜Provider Binding 当前撤销门文件级计划

基线：`m1@0a76e7e2`、Authority `AOS-001186`、权威库 `aos_current_preview_20260927@a0v_135` 只读。电脑重启后原卷、备份 SHA、PG/API/Web 健康已复核。依据 231、231-9、49-W6-01、128-W-L20 与 D-waves 的 E17-s3o-b 登记，当前只处理 ProviderCapabilityBinding 这一切片；AgentInstance 与 ToolBinding 分别另证，不以此波代替。

## 文件和顺序

1. `services/aos-api/tests/test_ecommerce_analyst_stage_review_authority.py`：在 disposable PG 用 `org-org/dev-project` 建立 exact CapabilityBinding、原 Resolver Receipt 和 READY Plan；撤销该绑定后，断言只读 Plan GET 变 BLOCKED、freeze 失败，且无 freeze Receipt。先跑 RED。
2. `services/aos-api/aos_api/aip_production_contract_store.py`：只在原 `_require_exact_assignee_resolution` 复用已有 Resolver 的候选判定，复核 Provider 当前绑定及 Receipt 中的 exact Binding refs，不新建第二套机器绑定判断。必须复用当前 tenant、binding ID、version、exact capability、状态、健康和 freshness；写准入时锁住当前绑定以挡住并发撤销，GET 不持写锁。不修改 Resolver Receipt、不引入租户全局替代绑定。
3. `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/w5cb4-e17-s3ob-*`：保存 RED/GREEN 命令和结果、相邻回归、方案一致性与局限。m1 精确提交后更新 Task/Delivery、Authority、Prime/01/06、D-waves 和下一波入口。

## 安全与退出

不调用 Provider，不写当前真实库，不启 Host/worker，不用 dev-org 正向实例，不读商城源或旧 Run。隔离库可删除，仅它是测试产物。通过条件是原正向仍 READY、撤销后 GET/freeze 失败封闭、并发删除不能越过写准入、租户隔离和相邻回归通过。若发现原 Provider 机制还要求独立发行身份或 ACL，记录并保持禁入；不靠测试 Binding 宣称正式六绑定或首链可执行。
