# W5cal｜A1 自然分析阶段只读发现接线验收

## 第 1/6 步：上位方案与现场

复习 231、231-9 BG-02/03、经营参谋 D01-D03 与栖月汇产品方案；本波计划及调用图审计见相邻 `w5cal-*plan/audit`。当前真实 PG 无 running TaskRun/AgentRun/MethodRevision/Insight/Decision/GrowthPlan；旧 12 Run 不可作为新 D01 来源或重播。既有分析 bootstrap/数据恢复存在，生产 Host 缺后续分析阶段领取。因无当前方法/来源/预算/模型批准，本波按已提交计划收紧为 Host 内**只读发现与阻断**，不宣称三阶段运行。

## 第 2/6 步：文件级最小范围

- `services/aos-api/aos_api/ecommerce_analyst_stage_runtime.py`：只读租户有界扫描原分析 Receipt 元数据，核对 exact Receipt hash、原 TaskRun、当前 dispatch/安装代际/epoch、Host live generation、Task/Plan 状态及既有 AgentRun；最多 100 行。输出 blocked/reconcile/awaiting-authority，后者也不是执行许可。
- `scripts/a0v_ecommerce_runtime_host.py`：新增一个 Host-owned readiness worker，跟随原 stop/host_ready/租约边界并写 status；没有 AgentRun、Provider、Task、商城源读取或 side effect。
- 两个既有 Host 测试文件只适配第四个 worker；新增 `test_ecommerce_analyst_stage_runtime.py` 覆盖旧代、围栏、暂停/终态、重复原 Receipt、已有 AgentRun、缺 live generation、100 行上界和租户 scope。

## 第 3/6 步：实现与安全复审

查询仅访问 AOS 受治理 Receipt/dispatch/runtime/AIP 运行元数据，使用既有 `connect_read_only`；不触碰商城原始表。任何旧代/暂停/终态被挡；已有 AgentRun、对账中或 Receipt 不一致进入 reconcile，不生成新 attempt。超过上界整体 overflow；异常使状态 fail closed。`awaiting-authority` 明确仍缺 method/source/approval/route/budget/capacity 和正式 stage Owner，不能自动执行。

## 第 4/6 步：专项与累计

`pytest` 覆盖新 scanner、Host、Host lease、DataRequirement、D01/D02/D03 worker、snapshot resume：**178 passed、9 skipped、7 warnings**。9 skipped 包括需 disposable PG 的图测试，不能算真实自然三阶段。`py_compile` 与 `git diff --check` 通过。没有启动 Host，没有收费 Provider 调用。

与计划的 RED 顺序有偏差：本波新测试与实现同批落地，没有保留“先失败再变绿”的独立运行证据；因此仅按最终专项/累计 GREEN 记账，不声称完成 RED-first。下一波需先记录 RED 再实现。

## 第 5/6 步：浏览器/真实门

本波纯 Host 后端状态接线，无 UI 修改；本机 8080 无监听，不能伪称浏览器验收。真实 PG 当前无合法 running TaskRun，且 A0-V 原路径仍冻结；未起真实 Host、未重放旧事件、未读取商城源、未做正向 canary。真实业务结果仍 **未验收**。

## 第 6/6 步：结论与下一波

本波只完成自然阶段候选的 Host 内只读发现和 fail-closed 状态可见性，**没有完成 D01→D02→D03、首链或商业建议**。下一波 W5cam 应直接补最早核心缺口：在一个当前合法的自然 TaskRun 上，证明同 cutoff 的 MethodRevision/指标来源/Actor/绑定/Route/Budget/Capacity 与 exact 原 Occurrence；经正式 AIP Owner 建唯一 D01 AgentRun，并用原 attempt Receipt 对账。证据不足则仅拒绝该次执行，同时继续首链可独立开发部分；禁止旧 12 Run 重发。旧快照完整行和退休仍后置待办。
