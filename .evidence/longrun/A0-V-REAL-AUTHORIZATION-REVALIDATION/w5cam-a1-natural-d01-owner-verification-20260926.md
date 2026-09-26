# W5cam｜A1 D01 Owner 发行预检阶段验收（有界收口）

## Rules 与目标

m1 单写者、不 push；plan→RED→最小实现→专项/累计→浏览器条件验收→一致性复审→verification→commit。旧 12 Run 不重发、不读商城源，230 L0 挂起，dev-org 仅零 canary；未知结果先冻结原键。W5cam 只交付可复用的发行预检，不宣称自然业务闭环。

## 第 1/6–3/6 步：方案、RED、实现

方案见同目录 `w5cam-a1-natural-d01-owner-plan-20260926.md`，已补第 2、3 步纠偏。已观察到来源包缺失 RED、marking 权限缺失 RED、唯一 Receipt reader 缺失 RED。实现范围：

- `services/aos-api/aos_api/ecommerce_analyst_d01_issuer.py`：精确 D01SourcePacket、当前成员/marking/DB 时钟与现有 Method/Eval/Metric/Query/EvidenceBundle/DisclosureGrant reader、稳定 AgentRun ID/key、原 AIP Owner 调用。远端 OpenFGA 配置时 fail closed。
- `services/aos-api/aos_api/ecommerce_analyst_portrait_inputs.py`：抽取公用 packet reader，原 D01 Worker 入口保持。
- `services/aos-api/aos_api/ecommerce_analyst_stage_runtime.py`：只读唯一当前 AnalysisRuntimeReceipt 发现；明确不等于原 Occurrence/Case/Run 授权。
- 两个对应 extension-runtime 测试补拒绝和唯一性覆盖。

## 第 4/6 步：测试

专项：`uv run --directory services/aos-api pytest -q tests/extension_runtime/test_ecommerce_analyst_stage_runtime.py tests/extension_runtime/test_ecommerce_analyst_d01_issuer.py tests/test_ecommerce_analyst_portrait_inputs.py tests/test_ecommerce_analyst_portrait_worker.py`，55 passed、3 skipped。`py_compile` 与 `git diff --check` 通过。

累计：`test_analysis_continuation_origin_pg.py`、`test_analysis_continuation_context_pg.py`、`test_aip_agent_run_execution_service.py`、`test_aip_agent_registry_store.py` 合计 34 passed、2 errors。错误均在 `test_analysis_continuation_origin_pg.py` fixture，经原 `AnalysisStartupEvidenceService.record` 的 `startup evidence chronology differs`；本波未改该文件和其调用链，暂列回归环境/fixture 时间线待查，不能记为全绿。未触碰真实业务 Run。

## 第 5/6 步：浏览器与方案/代码复审

本波没有已授权且具备真实 running TaskRun、MethodRevision、有效审批/预算的发行界面；不启动 Host、不调用收费 Provider，浏览器自然执行验收未进行。代码与方案一致：Receipt-only 检查不冒充完整原链；来源校验与 Owner 仍处在不同事务，存在撤权/来源漂移 TOCTOU，因此 `NaturalD01Issuer` **未注册到 Host，不可用于生产自然发行**。注入式单元测试的正例仅证明逻辑，非真实自然结果。当前实时权威缺口仍是 running TaskRun/MethodRevision/完整原始链同事务证明。

## 第 6/6 步：结论与下一波

本波有界完成“D01 发行预检”子范围，业务结果未完成；不将旧 12 Run 或现有商品表充当新的 D01 输入。下一波 W5can：先方案化 `AnalysisContinuationOrigin` → 精确来源包 → 原 AIP Owner 的同事务组合/Reader 选包，补隔离 PG 撤权、重复与未知提交测试；若现有 Owner 不支持共享事务，先做最小接口改造方案并保留 Host 关闭。原 fixture 时间线 2 errors 进待查，不抢占首链主线。
