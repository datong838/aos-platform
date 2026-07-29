# W3_W4_DONE · B5 智能体插件配置+连通测试

> 分支：`feature/223-worker-3`  
> 基线：`4a8ceb8`  
> 日期：2026-07-29  
> 目标：`/aip/capabilities` 55%→70%

## 适用 Rules

- 227 W4 并行：隔离工作树、严格所有权、禁 push/改 m1/merge、禁 Link*/Action*/DocumentIntelligence*/nav/main
- 用户规则：方案先行、最小改动、自测、中文交付
- commit：`w3(B5): ...`

## 改动文件

| 文件 | 说明 |
|------|------|
| `apps/web/src/pages/CapabilityPage.tsx` | 列表 live/demo；受控配置表单；PUT 保存；POST test 连通；失败标「演示路径」 |
| `apps/web/src/pages/CapabilityPage.test.ts` | 纯函数测（path/config/merge/localStorage/msg） |
| `services/aos-api/aos_api/aip_capabilities_engine.py` | 插件默认种子、upsert、test_connectivity |
| `services/aos-api/aos_api/routers/phase3_aip_capabilities.py` | PUT upsert；`POST /capabilities/test` |
| `services/aos-api/tests/test_phase3_aip_capabilities.py` | upsert + connectivity 用例 |
| `apps/web/src/styles.css` | 末尾 `/* === W4-B5 === */` |
| `W3_W4_B5_方案.md` | 实施方案 |
| `W3_W4_DONE.md` | 本交付说明 |

**未改**：`main.py`、`nav.ts`、Link*/Action*/DocumentIntelligence*。

## 验收要点

1. **列表优先 live**：`GET /v1/aip/capabilities` 成功 → 顶栏「真 API」；失败 → 「演示路径」+ 静态卡。  
2. **配置可保存**：面板「保存并启用」→ `PUT /v1/aip/capabilities/{id}`（upsert + config）；失败 → localStorage + 演示文案。  
3. **连通测试可用**：卡上/面板「测连通」→ `POST /v1/aip/capabilities/test`；失败 → 本地模拟 + 「演示路径」。  
4. **自测**：`CapabilityPage.test.ts` → **9 passed**；engine 直跑 upsert/test → OK（本机无 Postgres，完整 pytest/conftest 未跑）。

## 风险

- `GET /v1/aip/capabilities` 可能被先注册的 `wave_ext` 抢先；前端已兼容 `{id,kind,endpoint}` 与 phase3 `{name,config,...}`。PUT/test 走 phase3（ensure+upsert）。  
- 连通测试为进程内健康模拟，不真实外呼。  
- 本机无 Postgres 时 `pytest` 因 conftest→db 失败；引擎逻辑已直跑验证。

## 建议下一批 226 页面

- `aip-capabilities.html` ↔ `/aip/capabilities`（配置面板间距/边框与视觉稿对账）

## 回滚

`git revert` 本分支 `w3(B5):` commit。
