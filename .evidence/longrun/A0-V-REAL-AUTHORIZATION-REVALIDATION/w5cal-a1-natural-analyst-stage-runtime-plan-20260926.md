# W5cal｜A1 自然分析三阶段运行接线方案（首链核心）

## 复习上位与最新现场

231 §12/14、231-9 BG-02→03/04 与产品方案要求“商品更新/批准周期→Occurrence→Case/Run→经营参谋真实建议→exact 评审→内部内容任务”，不能只交付可点页面、测试或孤立 DTO。W5cai 只读见历史 26 READY Dataset Receipt；最晚 9 月 17 日，不能当今天新鲜事实。W5caj/k 完成销售武器包草稿与现有内容 Task 的包内映射，但尚无权威发布/自然业务执行。

静态调用图和当前 AOS PG `a0v_092` 只读证明：`scripts/a0v_ecommerce_runtime_host.py` 当前仅启动 product-event、analysis-data-requirement、baseline-assessment 三个业务 worker；D01 `PortraitTaorWorker`、D02 `DiagnosisTaorWorker`、D03 `GrowthPlanTaorWorker` 只有定义/测试，没有生产调用者。分析 bootstrap 会有意把初始 TaskRun 暂停且不创建 AgentRun；后续 DataRequirement 恢复入口存在，但缺自然三阶段领取/建 AgentRun/调用链。当前同租户 `aip_task_run` 0 running、`aip_agent_run` 0、`GrowthPlan` 0、四类评审 `aip_artifact` 0；旧事件/Receipt 不可手工重放。故**第一核心缺口是三阶段生产调度，不是旧 12 Run 每行或销售 Brief 本身**。

## 串行 1–6 与文件级范围

1. **冻结精确调用合同**：读 `ecommerce_analysis_snapshot_resume.py`、`aip_business_investigation_compile_receipt`、`AipAgentRunService.create/transition`、D01/02/03 worker、Runtime Host 和 Provider/预算/能力权限。用只读 SQL/现有测试证明 TaskRun→business Run→原 Occurrence→安装代际/epoch 的唯一反向链、AgentInstance/Skill/Logic/Route 当前性及 1→2→3 stage 状态。找不到同事务/current authority 则 STOP，不编猜测桥。
2. **最小设计与 RED**：新增 `services/aos-api/aos_api/ecommerce_analyst_stage_runtime.py`，只提供一个 Host-owned 有界发现、精确资格与先读 Receipt 的 stage 调度；不复制 AIP Task/AgentRun/TAOR 权威。测试 `services/aos-api/tests/extension_runtime/test_ecommerce_analyst_stage_runtime.py` 先覆盖旧代、跨租户、已结束/paused Run、缺完整前驱、重复领取、Provider unknown、无当前批准/预算/能力、失租和取消。原 `Portrait/Diagnosis/GrowthPlanTaorWorker` 不改权限门，只有证明现有接口不足才最小补。
3. **运行时接线**：在 `scripts/a0v_ecommerce_runtime_host.py` 注册单一新 worker；Host `host_ready`/stop/lease 控制贯穿，默认不因代码存在而开启真实 Provider。`AipAgentRunService` 的当前绑定、容量预留、幂等 Receipt 和当前有效权限是唯一建 Run 路径。未知提交/Provider 结果先查原 attempt/Receipt，绝不新 ID 重发。
4. **专项与累计**：隔离 PG 中完成 D01→D02→D03 不含真实 Provider 的 Owner/Receipt/重启/重复事件回归；再验证现有 D01/02/03 worker、Occurrence、Handoff 及租户 canary。明确 mock/fixture 只证明代码，真实自然链另验。
5. **浏览器/真实门**：没有当前 A0-V 安装、数据水位、模型/预算批准前，仅浏览器只读看当前状态；不得起真实 Runtime Host 或调用收费模型。获得当前门后另波自然运行至少两批、人工 exact 评审及可读内容产物；不能开发者手工拼内部接口。
6. **收口**：verification、AOS/D-waves/Prime 同步、m1 精确提交，下一波继续首链最早阻断处。旧 12 Run 正式退休列维护待办；不读商城源、不重发、230 L0 挂起、dev-org 零 canary、不 push。

停止条件：任何原 Task/Occurrence/安装映射不唯一、维护围栏无法保持、当前授权/容量不可证、执行结果未知、DB 与包合同不一致，停对应真实动作并留原状态；无副作用代码/隔离测试可继续，不扩大全项目停工。

## 2026-09-26 第 1 步复核后的实施收窄

当前 PG 没有 running TaskRun、MethodRevision、Insight/Decision/GrowthPlan，也没有合法的自然 D01 输入。因而本波不得宣称完成三阶段执行、不得伪造 D01 方法/来源或从旧事件重放。第 2–4 步先落一个 **Host 内只读、租户有界的 stage discovery/readiness worker**：扫描原分析 Receipt 和当前 dispatch/runtime/TaskRun，输出明确的 `blocked`/`reconcile`/`awaiting-authority` 状态；只向 Host 报状态，不建 AgentRun、不开 Provider、不推进 Task。无完整 authority 时永不返回“可执行”。专项测试覆盖有界、跨租户、旧代、暂停/终态、重复/unknown 和缺前驱。Host 接线只影响监测，不视为真实运行授权。D01 真实 provision/execute 与 D02/D03 串联单列下一波的最早核心阻断，不能用本波绿色测试冒充闭环。
