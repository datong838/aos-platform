# W3_W3_DONE · C3 属性编辑 + C4 Function

> 分支：`feature/223-worker-3`  
> 基线：`b7c8760`  
> 日期：2026-07-29  
> 目标：属性编辑 50%→70%；Function 45%→65%

## 适用 Rules

- 227 W3 并行：隔离工作树、严格所有权、禁 push/改 m1/merge、禁 Wiki*/ObjectType*/pipeline*/source*/nav/main
- 用户规则：方案先行、最小改动、自测、中文交付
- commit：`w3(C3C4): ...`

## 改动文件

| 文件 | 说明 |
|------|------|
| `apps/web/src/pages/s2/PropertyEditorPage.tsx` | 列映射 Tab UI；automap/保存映射；properties API 映射；live/demo |
| `apps/web/src/pages/s2/PropertyEditorPage.test.ts` | C3 映射/转换纯函数测 |
| `apps/web/src/pages/s2/FunctionEditorPage.tsx` | 列表/保存/试跑接线；参数表+试跑面板；演示角标 |
| `apps/web/src/pages/s2/FunctionEditorPage.test.ts` | C4 API↔UI / 试跑结果映射测 |
| `services/aos-api/aos_api/routers/phase4_ontology_types.py` | `PUT .../column-mapping` |
| `services/aos-api/aos_api/routers/phase4_ontology_functions.py` | `GET /functions`；Update 含 params；`POST .../test` |
| `apps/web/src/styles.css` | 末尾 `/* === W3-C3C4 === */` |
| `W3_W3_C3C4_方案.md` | 实施方案 |
| `W3_W3_DONE.md` | 本交付说明 |

**未改**：`main.py`、`nav.ts`、Wiki*/ObjectType*/pipeline*/source*。

## 验收要点

1. **C3 列映射 Tab**：切到「列映射」见源列/目标属性表；可改下拉；Automap 调 `POST .../automap`；保存调 `PUT .../column-mapping`。  
2. **C3 属性**：`GET .../properties` live 加载；新建走 `POST`；失败标 **「演示路径」**。  
3. **C4 参数表**：配置 Tab 可增删改参数。  
4. **C4 试跑**：测试 Tab + payload；优先 `POST .../test`；失败 `simulate` + **「演示路径」**。  
5. **C4 保存**：`PUT /v1/ontology/functions/:id`（含 params）。  
6. **自测**：`PropertyEditorPage.test.ts` + `FunctionEditorPage.test.ts` → **71 passed**。

## 风险

- 属性元数据无 PUT：已有属性「保存」仅本地更新，文案提示；列映射走独立 PUT。  
- Function 引擎未 seed 时列表为空仍为 live（不以空列表判 demo）。  
- 本机无 Postgres 时未跑 FastAPI 集成测；引擎/路由源码已核对。  
- `styles.css` 中既有 `.obs-source-banner__text` 缺 `}` 为基线遗留，本波未动。

## 回滚

`git revert` 本分支 `w3(C3C4):` commit。
