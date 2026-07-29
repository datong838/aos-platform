# W3_W2_DONE · A6 容量 + A7 模型目录

> 分支：`feature/223-worker-3`  
> 基线：`ad2241a`  
> 日期：2026-07-29  
> 目标：capacity 40%→60%；model-catalog 45%→65%

## 改动文件

| 文件 | 说明 |
|------|------|
| `apps/web/src/pages/s2/CapacityPage.tsx` | live/demo；接 usage / project-limits / user-limits；演示路径角标 |
| `apps/web/src/pages/s2/CapacityPage.test.ts` | 桶聚合 / limit 映射 / live 判定（30 passed） |
| `apps/web/src/pages/s2/ModelCatalogPage.tsx` | live/demo；接 model-admin/models 或 catalog+registered；register 写回 |
| `apps/web/src/pages/s2/ModelCatalogPage.test.ts` | API 行映射 / 能力归一 / 价格格式（32 passed） |
| `services/aos-api/aos_api/routers/model_capacity.py` | `GET user-limits` 无 userId 时返回 `{items,count}` |
| `apps/web/src/styles.css` | 末尾 `/* === W2-A6A7 === */` 角标样式 |
| `W3_W2_A6A7_方案.md` | 实施方案 |
| `W3_W2_DONE.md` | 本交付说明 |

**未改**：`main.py`、`nav.ts`、Analyst/Observability/Studio/Publish/Capability。

## 验收要点

1. **A6 live**：`GET /v1/aip/capacity/usage` 成功 → 今日/周/月桶由日维度聚合；项目 RPM/TPM 来自 project-limits；用户表来自 user-limits 列表（可空）。  
2. **A6 demo**：usage 失败 → MOCK + **「演示路径」**。  
3. **A7 live**：优先 `model-admin/models`，失败回退 catalog+registered；注册走 `POST .../register`。  
4. **A7 demo**：API 失败 → MOCK + **「演示路径」**。  
5. **自测**：`CapacityPage.test.ts` + `ModelCatalogPage.test.ts` **62 passed**。

## 风险

- 按模型「登记限制」表无后端 API，live 仍展示本地示意行（非整页演示）。  
- 用户限额无预算字段 → live 下日预算/今日已用为 0。  
- 本机无 Postgres 时未跑后端集成测；router 源码已核对列表分支。  
- 若旧 aip_*_router 遮蔽 phase2 path，前端会降级演示路径。

## 回滚

`git revert` 本分支 `w3(A6A7):` commit。
