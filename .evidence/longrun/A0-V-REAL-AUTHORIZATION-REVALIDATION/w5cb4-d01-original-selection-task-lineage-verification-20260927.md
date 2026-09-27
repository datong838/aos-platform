# W5CB4 D01 原选择引用进入分析 Task verification（2026-09-27）

## 第 1/9–2/9 步：方案和文件级清单

按 231 A1-02/03、231-9 BG-02/03 以及 `w5cb4-d01-current-packet-selection-plan-20260927.md`，复核原分析 Context 中的 SourceSelection Owner：`AnalysisContextPreparation` 在同一原事务读/核 `sourceSelectionRef`，但 `prepare_analysis_task` 创建 Task 时遗漏公共 `selection_ref`。只补原来源选择谱系，不声称 Method/Metric/Query/DisclosureGrant 完整包或执行许可。涉及 `ecommerce_analysis_context_preparation.py`、`ecommerce_analysis_task_preparation.py` 及 `test_analysis_task_preparation_pg.py`；不新增表、Run、Host 接线或 Provider 调用。

## 第 3/9–4/9 步：RED→最小实现

隔离 PG RED：要求 Task 保留原 `SourceSelectionRevision` 身份时，旧 `prepare_analysis_task` 不接受 `selection_ref`，4 项失败。实现使原 Context 把已核的 `PipelineExactRef` 传给 Task Owner；只接受该精确类型与 SourceSelectionRevision，Task 以现有 `selectionRef` 列持久化 ID/修订，并在 Owner 回读后比较。缺失/错类型在写前拒绝；Task 同键重放仍原结果。内容哈希仍由原 SourceSelection Owner/原链回读负责，Task 的通用 ResourceRef 本身不充当完整 exact 授权。

## 第 5/9–6/9 步：专项与累计

`test_analysis_task_preparation_pg.py`：6 passed；扩大到 Task/Context/编译/原链邻接 35 passed；再纳入启动 Evidence PG 共 **43 passed**。7 条既有字段/兼容 warning。`py_compile`、`git diff --check` 通过。PG fixture 使用隔离测试库并按夹具清理，不影响当前业务库。`dev-org` 继续只作为负向测试作用域。

## 第 7/9 步：浏览器与一致性复审

无前端变更、未启用 Host，本波浏览器交互 N/A；当前安全预览保持禁入。代码与计划一致：没有按最新记录猜来源，没有把 Task selectionRef 当 D01 packet，没有读取商城源，也没有手工创建真实 Run。原 `aip_task.selection_ref` 已存在，无迁移。旧任务保持原记录不回填；若重放旧相同 key 而原 Task 无选择引用，Owner readback 拒绝，必须只读对账，不换键补发。

## 第 8/9–9/9 步：结论与下一波

本切片完成原事件选择→分析 Task 的必要谱系连接，不代表 D01 packet selector/自然首链完成。下一波继续在原批准来源 Owner 冻结同 TaskRun/Plan/cutoff 的 Method/Metric/Query/EvidenceBundle/DisclosureGrant exact 包选择引用，先审正式 Evidence/Disclosure Owner 与撤权语义，再写零/多/跨租户/过期/撤权/未知提交 RED 与最小持久 Owner；没有合法来源只阻断该实例并继续 BG-00 配置研发。Host/Provider 关闭，旧 12 Run 不重播、不读商城源、230 L0 挂起、m1 单写不 push。

Prime/AOS 记忆：上次检查 `memory-status` 为 GREEN_WITH_WARNINGS、`memory-validate` GREEN，但 Prime 投影仍是 AOS-000802 旧状态；当前切片写 AOS 上下文/D-waves，不把旧投影宣称当前同步。
