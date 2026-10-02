# GW-b-2c2c1b3c2d2b3c1｜生成宿主原 Stage Owner 引用验证

基线 `AOS-001129` / `m1 9b6cc63e`；先写 `w5cb4-gwb2c2c1b3c2d2b3c-original-owner-join-plan.md`，遵 231-5 §9 和 D-waves d2b3c。这里只收原 Stage Owner 精确引用子波，完整 d2b3c 仍待原 BI、runtime/Eval/permission 与两个消费者联合。

- RED：原 PG producer `source` 产生 draft、原 accepted StageDecision 和正式 Owner 获批 successor 后，调用 `ContentGenerateHostService._accepted_stage_owner_refs` 报 `AttributeError`，1 failed/20 deselected，退出1。
- 最小实现：同一 `HostTransaction` 调原 `ReviewAdvanceHostService._revalidate_accepted_stage_source`，从原当前 Decision 与获批 Plan 对象重建 8 项阶段精确引用；对照候选，拒来源种类错误和 Artifact 漂移。输入虽由待核候选提供，却不是从 Receipt/Task/Brief 自身取 expected；原 Owner 回读负责当前性、获批业务内容、撤销/期限及租户校验。没有复制 Owner 状态机。
- `test_analyst_stage_handoff_source_pg.py`、`test_ecommerce_review_task_brief_authority_pg.py`、`test_ecommerce_content_generate_handoff_lineage.py` 在 signed preview preflight 指向的独立 `aos_test_*` 可销毁 PG 上 `49 passed, 7 warnings`，退出0；`py_compile`、`git diff --check` 退出0。测试 fixture 决定不等于当前真人批准。
- 复审限制：此方法尚未被新 Receipt/TaskBrief 消费者调用；原 BI Analysis Receipt 与 Stage runtime/Eval/permission 无完整 producer 正向；当前真实库未写，Host/worker/Provider 禁入，不能称生成 Host、原 Review Handoff 或首链可执行。可读 Artifact 和人工评审消费者仍未接。

下一步 d2b3c2：先用原 BI AnalysisRuntimeReceipt 和当前 Case/Occurrence producer 在隔离 PG 同事务接 Stage TaskRun/Plan/Eval/permission，再把这组 Owner-verified expected 交给现有 Review Receipt 与 v3 Task/Brief 读者。若原生产者配置不足，明确保留该具体实例禁入，不用 fixture 造当前业务正例。

提交后补证：`aos-platform/m1@14b52259`，`launchctl kickstart -k` 重载 API/Web 后 PID39963/39966；首个即时健康探针遇启动瞬态 connection refused，随后同一 PID 的 `/v1/health`、`/v1/ready` 和 Web 页面均 HTTP200。Codex 浏览器等异步目录加载后仍见37项仅已评测、已发布0、三项发布来源缺失、按钮 disabled、无电商工作台入口。此读者切片没有改变业务准入。
