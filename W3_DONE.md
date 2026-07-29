# W3_DONE · A3 Draft 真审批链路

> 分支：`feature/223-worker-3`  
> 日期：2026-07-29  
> 目标：`/aip/drafts` 55% → 75%

## 改动文件

| 文件 | 说明 |
|------|------|
| `apps/web/src/pages/DraftInboxPage.tsx` | live/demo 双路径；approve/reject 走 SDK；API 行映射 + timeline 合成；「演示路径」角标 |
| `apps/web/src/pages/DraftInboxPage.test.ts` | 补 `mapApiStatus` / `mapApiRowToDraftItem` / timeline 断言（66 通过） |
| `services/aos-api/aos_api/aip_drafts_engine.py` | 7 态状态机 + timeline；保留 draft→approve/reject 兼容旧测 |
| `services/aos-api/aos_api/routers/phase3_aip_drafts.py` | camelCase 响应、详情、transition；approve/reject 回写 timeline |
| `apps/web/src/styles-di-bridge.css` | `/* W3-A3 */` 数据源角标样式 |
| `W3_A3_方案.md` | 实施方案 |
| `W3_DONE.md` | 本交付说明 |

## 验收要点

1. **有后端（live）**：`listDrafts` 成功即用真实列表（可空）；批准/驳回调用 `approveDraft`/`rejectDraft`，成功后刷新列表与 timeline。  
2. **无后端（demo）**：降级 MOCK，顶栏标明 **「演示路径」**；本地状态机仍可用。  
3. **状态映射**：Wave-3 `proposed` → UI `in_review`（露出批准/驳回）；终态 `approved`/`rejected` 归入对应 Tab。  
4. **状态机**：前端 7 态不变；后端引擎对齐并兼容既有 `test_phase3_aip_drafts.py`。  
5. **自测**：`DraftInboxPage.test.ts` 66 passed；`test_phase3_aip_drafts.py` 9 passed。

## 风险

- 生产 `GET/POST /v1/aip/drafts*` 仍由 Wave-3 `drafts.py` / `runtime_write` 优先注册；Phase3 同 path 可能被遮蔽。前端以 ontology-sdk（Wave-3）为准，引擎增强供单测与解耦后使用。  
- Wave-3 无原生 timeline → 详情区合成最小历史；刷新后终态正确。  
- live 下「退回修改/撤回」等非 approve/reject 仅改本地视图，不持久化（主验收为批准/驳回写回）。

## 回滚

`git revert` 本分支 `w3(A3):` commit 即可。
