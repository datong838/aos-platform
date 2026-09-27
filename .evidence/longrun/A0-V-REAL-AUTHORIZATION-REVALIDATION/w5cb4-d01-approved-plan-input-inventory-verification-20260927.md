# W5CB4 D01 批准 Plan 首步来源集合门（2026-09-27）

## 当前结论

原批准 `PlanRevision.steps[0].inputRefs` 可作为 D01 portrait 步的正式来源**集合**权威。未注册 `NaturalD01Issuer` 现要求该集合非空、无重复，且与 D01 AgentRun 声明的 exact 引用身份集合相同；后者原本已须与 `D01SourcePacket` 一致。空、少、额外、重复引用均在原 AgentRun Owner 创建前拒绝。此检查复用 Plan 的原内容哈希及批准状态，无新表、无真实业务写。

该 Plan 集合不含完整 hash、指标／查询／Bundle 对应关系、截止面、markings、每条 Evidence 的披露决定和读取窗口，因此**不是**完整 packet 选择 Receipt。各 Method／Query／Evidence／Disclosure Owner 分立，当前编译 Receipt 也没有完整包。本子波不能放开 Host、Provider、预算或自然运行。

## 验证与范围

1. 方案先补 `w5cb4-d01-current-packet-selection-plan-20260927.md`；4 个负例先 RED（均 `DID NOT RAISE ValueError`），修复后 D01 专项 `32 passed`。
2. 累计：`uv run --directory services/aos-api pytest -q tests/extension_runtime/test_ecommerce_analyst_d01_atomic.py tests/extension_runtime/test_ecommerce_analyst_d01_issuer.py tests/extension_runtime/test_analysis_continuation_origin_pg.py tests/extension_runtime/test_analysis_task_preparation_pg.py tests/aip/test_aip_agent_run_execution_service.py --tb=short` → `64 passed, 7 warnings`。
3. `git diff --check` 通过。安全预览 8434 HTTP 200；8080 根路径 404 但端口可达；18181 无监听。此未注册后端代码没有浏览器交互入口，故不以页面状态冒充业务验收。
4. 未接触商城源、旧 Run、`dev-org` 业务数据；未用调用者的 packet 越过批准 Plan 集合。另一测试文件和两个测试环境旁证文件为既有工作树改动，均未纳入本波提交。
5. Prime Agent 安全服务 `com.aos.prime-agent-safe` 为 running；共享记忆 status `GREEN_WITH_WARNINGS`、validate `GREEN`。其正式 project revision 仍为 `AOS-000802`，只证明旧投影健康，**未**把本波误同步为正式 Prime Delivery Receipt；本波新鲜上下文在 227/228 与 D-waves 已记。

## 下一波

完整 D01 packet 选择权威仍缺：先冻结同 TaskRun／Plan／cutoff 的结构化关系、Grant/marking/窗口、选择者及同键幂等 Receipt；不能将现有 Plan 集合误当完整批准。只读审计现有原 Owner 能否承载，若无则新增窄选择 Owner、隔离 PG 负向和原事务读回。与此同时按 231 主序推进 BG-00 最小合法绑定／配置，不为了 D01 包拖延其他首链主线。
