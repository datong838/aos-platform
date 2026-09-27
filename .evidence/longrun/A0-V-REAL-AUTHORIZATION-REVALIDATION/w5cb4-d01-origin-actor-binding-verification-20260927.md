# W5CB4 D01 原链 actor 绑定 verification（2026-09-27）

## 第 1/9–2/9 步：上位方案和文件级计划

依据 231 A1-02/03、231-9 BG-02/03 与栖月汇黄埔 0 期首链，复习 W5cam/W5can D01 未注册同事务接线；文件级计划见 `w5cb4-d01-origin-actor-binding-plan-20260927.md`。起点 m1 `055f847f`；用户原有测试改动和 w5c8i 两文件未碰。仅改 `ecommerce_analyst_d01_atomic.py` 及其专项测试。

## 第 3/9–4/9 步：RED→最小修复

RED：新增两项测试，外部发行 actor 与原 AnalysisContinuationOrigin 的源 actor 不同、或源 actor 缺失时，原代码均**未拒绝**（2 failed）。修复在连接和任何 Owner/来源读前精确比较 `origin.context.analysis.source.actor` 与本次 actor；不同/缺失抛 `PermissionError`，正常 actor 原路径不变。测试同时记录 connect，确保拒绝发生在数据库连接之前。没有改公共 AIP Owner、原键、事务提交或任何 Host/Provider 开关。

## 第 5/9–6/9 步：专项与累计

`uv run --directory services/aos-api pytest -q tests/extension_runtime/test_ecommerce_analyst_d01_atomic.py tests/extension_runtime/test_ecommerce_analyst_d01_issuer.py tests/extension_runtime/test_analysis_continuation_origin_pg.py tests/aip/test_aip_agent_run_execution_service.py`：**51 passed**，7 条既有字段/兼容 warning。`py_compile` 和 `git diff --check` 通过。第一次累计命令误写了不存在的测试文件名，退出 4、没有执行测试；用 `rg --files` 核准真实路径后完整重跑为上述 51 passed，未把前次计绿。

## 第 7/9 步：运行与方案/代码复审

本波未新增前端或注册 Host，浏览器业务验收不适用；安全 8080 OpenAPI=200、8434 页面 HTTP=200、18181 无监听。对照方案：修复仅收紧原 actor 身份，不改变来源 packet 的权限/新鲜度验证，不读取商城源、不创建 AgentRun、不调用 Provider。拒绝路径未入 DB，正常路径和未知提交原键测试仍通过。**这不是 D01 生产 selector 或自然业务结果**。

## 第 8/9–9/9 步：退出与下一波

当前 D01 packet 的 Method/Metric/Query/EvidenceBundle/DisclosureGrant exact 闭包未持久绑定到现有 Plan/编译 Receipt；不能靠“最新一条”自动选择，须先在原批准来源 Owner 上冻结明确包/选择引用，再让未注册 coordinator 在同事务消费。下一波方案先行，沿 `aip_task_models.py` 的 Task selection_ref、原 AnalysisCompilation/Brief 与 `ecommerce_analyst_d01_issuer.py` 查最小 Owner 接线；RED 覆盖零/多/跨租户/过期/撤权、错 Plan/Receipt，禁止新建第二事实权威或用测试 fixture 冒充。当前库预算/路由/发布均未具备，Host/Provider 保持关闭；可独立继续 BG-00 正式配置 Owner 的安全开发。旧 12 Run 退休和非首链历史逐行证明继续后置。

记忆状态：`memory-status` 返回 GREEN_WITH_WARNINGS、`memory-validate` GREEN，但 Prime 投影仍停在 `AOS-000802` 的旧 P2g 负向门；本波先更新 AOS 上下文/D-waves，不把旧投影称当前同步。m1 单写、不 push；230 L0 挂起，`dev-org` 仅零 canary。
