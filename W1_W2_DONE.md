# W1_W2_DONE — A4 分析师真查询路径

## Commit

分支 `feature/223-worker-1` · 信息：`w1(A4): analyst live query path with demo fallback`  
（完整 hash 以 `git rev-parse HEAD` 为准，交付回复中给出。）

## 改了什么

| 文件 | 变更 |
|------|------|
| `W2_A4_方案.md` | 方案文档（先方案后代码） |
| `services/aos-api/aos_api/aip_analyst_query.py` | **新建** 内存表 SELECT/NL 引擎 |
| `services/aos-api/aos_api/routers/aip_analyst.py` | **新建** `POST /v1/aip/analyst/query` |
| `services/aos-api/aos_api/main.py` | **仅** `# W2-A4` import + `include_router` |
| `services/aos-api/tests/test_aip_analyst_query.py` | **新建** 引擎 + HTTP 单测 |
| `apps/web/src/pages/s2/AipAnalystPage.tsx` | 运行走 API；失败黄条演示路径 + MOCK |
| `apps/web/src/pages/s2/AipAnalystPage.test.ts` | 映射/降级单测 |
| `apps/web/src/styles.css` | **仅末尾** `/* === W2-A4 === */` banner |
| `W1_W2_DONE.md` | 本交付说明 |

**未改**：Observability/Capacity/ModelCatalog/Studio/Publish/Capability、nav.ts、routes。

## 如何自测

```bash
# 前端（需 nvm node）
export PATH="$HOME/.nvm/versions/node/v20.20.2/bin:$PATH"
cd apps/web && npm test -- src/pages/s2/AipAnalystPage.test.ts
# → 59 passed

# 后端（需本机 PG :5433）
cd services/aos-api && python3 -m pytest tests/test_aip_analyst_query.py -q
```

本机无 PG 时：引擎/路由已用 importlib 绕过 `aos_api.__init__` 冒烟通过（live shops / NL inventory / DELETE→400）。

## 验收对照（227 · A4）

- [x] SQL 真查询路径：`POST /v1/aip/analyst/query` → `source: live`（内存 shops 等）
- [x] NL 真查询路径：`naturalLanguage` → 映射 SQL → live
- [x] 失败/API 不可达：前端黄条「演示路径」+ 本地 MOCK
- [x] 后端 fallback 未知表仍 200 + `source: fallback`（前端亦标演示）
- [x] main.py 最小两处注册
- [x] 不碰禁止文件

## 风险

1. live 为内存表，非真实 DB；契约已稳定，后续可换 PG。
2. 标准 pytest 依赖 `aos_api` 导入链连 PG；无库时需起 `deploy/dev` 或等价。
3. Planner 合并 `main.py` / `styles.css` 末尾时注意冲突。
