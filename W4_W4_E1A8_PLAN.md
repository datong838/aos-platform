# W4 · E1+A8 方案（文档智能 35→55 · DocIntel 并入）

> 分支：`feature/223-worker-4` · 基线 `4a8ceb8`  
> 依据：`227-未完成项补齐计划.md` W4·E1+A8  
> 原则：最小改动；不新建侧栏；不碰 Link*/Action*/Capability*/main.py

## 1. E1 决策（已定）

| 项 | 决策 |
|----|------|
| `pipeline-doc-intel.html` | **并入** `/aip/doc-intelligence`，**不**新建独立菜单/页面 |
| 侧栏 | 保持现有「文档智能」一项；**勿**新增 DocIntel 管道 nav |
| 残留路由 | 可选：`/data/pipeline-doc-intel`、`/pipelines/doc-intel` → 重定向到 `/aip/doc-intelligence` |

## 2. 验收对照

| 任务 | 目标 | 本波动作 |
|------|------|----------|
| **A8 文档智能** | 抽取/流水线至少一条真 API；失败标「演示路径」+ MOCK | 接线 `POST /api/aip/docintel-extract/run`（优先）；失败回落 `MOCK_EXTRACT_FIELDS` + 角标 |
| **E1** | 决策落地 | 说明条「DocIntel 管道能力收敛于此页」+ 轻量管道能力条（Input→LLM→Output + 试运行）；可选重定向 |

## 3. A8 · 真 API 路径

### 3.1 已有 / 最小后端

| 端点 | 说明 |
|------|------|
| `POST /api/aip/docintel-extract/run` | **本波新增**（同 router，不改 main）：按 template + text 返回 `fields[]` + `demo:false` |
| `POST /v1/docintel/pipeline` | 已有 wave_ext；E1 试运行优先走此路径，失败标演示 |

抽取主路径：`/run`。前端按钮「运行抽取」调用；页载时对当前选中文档尝试一次（静默失败→演示）。

### 3.2 前端行为

1. `dataMode: live | demo | loading`
2. 成功：`live` + 用 API fields 更新提取表；OCR 可从 `text`/`ocr` 回填
3. 失败：`demo` + `MOCK_EXTRACT_FIELDS` + 角标「演示路径」
4. 不改状态机主流程；审核/上传本地逻辑保持

### 3.3 纯函数（可测）

- `pathLabel(mode)` / `buildExtractPayload(doc, templateId)`
- `normalizeExtractFields(raw)` / `demoExtractFields(templateId)`
- `DOCINTEL_PIPELINE_TEMPLATES`（视觉稿 6 模板名，仅展示/试运行参数）

## 4. E1 · UI 增量（最小）

1. PageChrome 下说明条：`DocIntel 管道能力收敛于此页（原 pipeline-doc-intel，不单独建菜单）`
2. 轻量管道条：节点 `输入 → Use LLM → 输出` + 「试运行」调 `/v1/docintel/pipeline`
3. `styles.css` 末尾 `/* === W4-E1 === */` 徽章/说明条样式
4. `nav.ts` 仅注释：DocIntel 管道并入文档智能
5. App 可选两条 `Navigate` 重定向

## 5. 文件边界

| 文件 | 改动 |
|------|------|
| `apps/web/src/pages/s2/DocumentIntelligencePage.tsx` | A8+E1 |
| `apps/web/src/pages/s2/DocumentIntelligencePage.test.ts` | 新纯函数测 |
| `services/aos-api/aos_api/aip_docintel_extract.py` | `run_extract` 引擎方法 |
| `services/aos-api/aos_api/aip_docintel_extract_router.py` | `POST /run` |
| `apps/web/src/App.tsx` | 仅重定向（最小） |
| `apps/web/src/nav.ts` | 仅注释 |
| `apps/web/src/styles.css` | 末尾 W4-E1 |
| `W4_W4_E1A8_PLAN.md` / `W4_W4_DONE.md` | 方案 + 交付 |

**禁止**：push、改 m1、merge、碰 Link*/Action*/Capability*/main.py

## 6. 风险与回滚

- `/run` 为启发式字段填充，非真实 LLM → 仍属真 API 响应；联调无密钥时前端可走 live
- 重定向路径若无人使用无副作用
- 回滚：还原上表文件即可
