# WORKSHOP-R3-06 任务总控右侧复盘三段 · 验证记录

- 门禁：`WORKSHOP_PRODUCT_REMEDIATION_R3` / `R3-06`
- 任务：`WORKSHOP-R3-06-COCKPIT-REVIEW-ADVICE-WIKI`
- 基线 revision：`AOS-000462`
- 执行者：`m1`（用户全量授权直接在 `m1` 开发，接续 codex 进度）
- 日期：2026-09-03

## 1 上位方案依据

- 视觉源：`docs/palantier/foundry/html/workshop-task-cockpit.html` 右 1/3 栏三段固定结构。
- 施工范围：八菜单缺陷清单「R3-06 右侧复盘三段精确施工范围（2026-09-03）」。
- 视觉稿中的「有效 6 · 待定 1 · 有害 1」、`CN-05`、`AFT-03`、`VIP3过敏处理SOP · v3` 均为示例文案，实现一律未复制（浏览器取证 `forbiddenSampleText` 为空）。

## 2 canonical 数据来源（三段独立读取、独立失败关闭）

| 段落 | 权威来源 | 消费字段 |
| --- | --- | --- |
| 今日复盘 | 已解析的 Task Cockpit core `items` + `taskCutoff` | `status` 终态四值、`run.status`、`run.finishedAt`、`version` |
| AI 改进建议 | `GET /v1/aip/memory-authority/improvement-observations` | `conclusion`、`metrics`、`quality`、`limitations`、`cutoffAt`、`observationHash`、`agentInstanceRef`、`evalContractRef`、`evalReportRef` |
| 经验沉淀 Wiki · 今日入库 | `GET /v1/aip/memory-authority/candidates`、`GET /v1/aip/memory-authority/memories` | `status`、`scope`、`version`、`createdAt`、`quarantineReasons`、`request.candidateLayer`、`item.memoryLayer`、`revision.revision`、`revision.contentHash`、`revision.effectiveAt` |

未新增 SDK：复用既有 `apps/web/src/api/aipMemory/client.ts` 的 `AipMemorySdk`，按 R3-05 的 `capabilityClient` 注入模式新增可选 `memoryClient` prop。

## 3 关键失败关闭口径

- **不冒充效果结论**：视觉稿的「有效／待定／有害」属 EffectReview/Eval 语义，core 响应不提供逐任务 EffectReview，因此每条复盘固定显示「尚无可验证效果结论」，并在详情写明「页面不据 Run 状态推断业务成效」。未用 `run.status=succeeded` 冒充「有效」，也未用 `failed` 冒充「有害」。
- **证据质量显式标注**：`conclusion=insufficient_evidence` 或 `quality != measured` 时追加「证据不足，仅作为观察，不得当作结论」并展开 `limitations`。
- **隔离原因可见**：`quarantined` 候选必须展示 `quarantineReasons`，不只报总数。
- **段落结构不塌陷**：任一段读取失败只在该段显示「权威读取失败」，保留三段标题；不回退成 blocker 列表、不补造条目。原先占据整段的 blockers 降为「复盘所需数据缺口 N 项」可展开明细。
- **Run 状态词表纠正**：新增 `RUN_STATUS_LABELS`，避免把 Run 状态套任务状态词表导致 `succeeded` 漏出英文或被误标为「待核对」。既有任务卡片第 430 行同类问题属既有缺陷，本波未改动，留待后续波次。

## 4 零副作用

- 三段全为只读呈现，未接线 `submitCandidate`／`approveCandidate`／`promoteCandidate`／`publishWiki`。
- 未创建 Plan/TaskRun、未派发、未发送、未发布、未改价、未调用 Provider。
- 浏览器取证 `writeControls` 为空数组；观测到的六次请求全部为 `GET`。

## 5 测试与构建（全部新鲜执行）

| 项目 | 命令 | 结果 |
| --- | --- | --- |
| 专项 | `vitest run src/components/workshop/TaskCockpitPage.test.tsx` | `31 passed (31)`（25 既有 + 6 新增） |
| 累计回归 | `vitest run` | `271 files / 2436 tests passed` |
| 类型 | `tsc --noEmit` | 无错误 |
| 生产构建 | `vite build` | `built in 2.02s`，仅既有 chunk-size 提示 |

新增 6 项测试覆盖：三段顺序与固定可见、当日筛选与不冒充效果结论、改进观察结论与证据不足标注、Wiki 当日候选与入库统计及隔离原因、三段各自读取失败仍保留结构、空态可信且零写调用。

TDD 记录：先写 6 项测试确认 RED（`6 failed | 25 passed`），再实现转 GREEN。

## 6 内置浏览器验收（CDP 只读）

脚本 `verify-browser.mjs`，报告 `browser-report.json`，截图 `01-cockpit-review-three-sections.png`、`02-review-column.png`。

租户 `org-org/dev-project`、`/workshop/cockpit` 实测：

- `sectionCount = 3`，`headings = ["今日复盘", "AI 改进建议", "经验沉淀 Wiki · 今日入库"]`，`aria-label` 与标题一致。
- 三个 canonical 接口均 `GET` `200`，返回 `[]`；因此三段显示的是**真实空态**而非静默失败——这点由「空态」与「权威读取失败」两套文案区分，已在专项测试中分别覆盖。
- `forbiddenSampleText = []`、`writeControls = []`。
- 未回归既有结构：KPI 带存在，底部共享能力带仍为 10 项。
- 每个端点被请求两次，源于 `apps/web/src/main.tsx` 的 `React.StrictMode` 开发期双调用，既有取数同样如此；`scenarioRequest` 请求序号守卫已防止旧响应覆盖新状态，非本波回归。

## 7 一致性复审结论

方案「R3-06 右侧复盘三段精确施工范围」六条逐条对齐：三段结构与顺序、三段 canonical 来源与字段、只读零副作用、空态与失败态、文件级范围、八步节拍。复审期间发现并修正 Run 状态词表缺陷（见 §3）。

排除范围核对：`apps/web/src/api/ecommerceWorkshop/parser.ts` 及其测试、`apps/web/src/pages/s2/ModelRuntimePage.test.tsx`、`services/aos-api/tests/test_ecommerce_operation_command_service.py`、`services/aos-api/tests/test_ecommerce_workshop_operations_api.py` 本波全程未读改，仍保持进入本波前的未提交状态。

## 8 结论

`WORKSHOP_R3_06_COCKPIT_REVIEW_ADVICE_WIKI_GREEN`。未修改业务数据、未触发外部副作用。下一项进入 `R3-07`。
