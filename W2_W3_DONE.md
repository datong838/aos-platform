# W2 Worker W2 · W3 C2 完成报告

## 状态

已完成（`feature/223-worker-2`，基线 `b7c8760`）

## 目标对照

| 验收项 | 结果 |
|--------|------|
| 元数据项补齐（向视觉稿 KV 靠拢） | ✅ Overview `BpPropGrid` 扩至 14 项（RID/PK/TitleKey/Plural/Backing/Sync/存储/创建人/分支/可见性/管道等） |
| 链接关系非纯 ASCII | ✅ SVG 节点/边图 + 结构化列表（Overview 预览 + Links Tab） |
| 保持现有 Tab/API；失败可降级 | ✅ 7 Tab 不变；详情 GET 失败用前端 `deriveOtDetailMeta` |
| 不碰禁止文件 / 不改 main.py | ✅ 仅扩已有 `ontology.py` GET + 新 helper |

## Commit

见 git log：`w2(C2): ...`

## 变更文件

- `W2_C2_方案.md` — 方案
- `W2_W3_DONE.md` — 本交付
- `services/aos-api/aos_api/ot_detail_meta.py` — 元数据派生
- `services/aos-api/aos_api/routers/ontology.py` — `GET .../object-types/{id}` 返回派生字段
- `services/aos-api/tests/test_ot_detail_meta.py` — 后端单测（需可 import；本机无 PG 时用 importlib 冒烟）
- `apps/web/src/pages/s2/ObjectTypeDetailPage.tsx` — 优先拉详情 API，失败回落列表
- `apps/web/src/pages/s2/objectTypeDetail.tsx` — KV 补齐 + Link SVG 图
- `apps/web/src/pages/s2/objectTypeDetail.test.ts` — 前端纯函数测
- `apps/web/src/styles.css` — 末尾 `/* === W3-C2 === */`

## 自测

| 项 | 结果 |
|----|------|
| vitest `objectTypeDetail.test.ts` | ✅ 6 passed |
| `build_ot_detail_meta` importlib 冒烟 | ✅ |
| pytest `test_ot_detail_meta.py`（经 `aos_api` 包） | ⚠️ 本机 PG:5433 未起；`aos_api` import 拉起 main 需 PG |

## 风险

- 派生字段非 Foundry 真值，后续可换真列而不改 UI 契约
- 中文显示名 plural 为简单拼接 `s`（演示级）
- OntologyPage 内嵌面板自动受益；未改其文件

## 回滚

还原 enrichment GET、前端图组件与 styles 附录即可。
