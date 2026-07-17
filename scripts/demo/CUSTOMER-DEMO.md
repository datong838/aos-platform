# 客户演示脚本（TB.8）· 15～20 分钟

> **对齐**：[70](../../../docs/palantier/20_tech/70-业务平台可演示优先计划.md) · [26 §12](../../../docs/palantier/20_tech/26-AOS目标态开发计划.md)  
> **故事**：WorkOrder 工单运营 · **本地 Docker**  
> **不讲**：Full Spoke / Helm / 现场 Ferry / 生产 IdP / Jupyter·产品 1.3

## 0. 开场前（你这边 · 2 分钟）

```powershell
cd c:\work\projects\wchat\aos-platform
powershell -File scripts\demo\start-local.ps1
powershell -File scripts\demo\run-demo-smoke.ps1
```

打开 http://127.0.0.1:5173/demo · 点「确保种子」

## 1. 演示顺序（对着客户）

| 分钟 | 页面 | 话术要点 |
| --- | --- | --- |
| 0–2 | `/` 概览 | 「AI 操作系统控制面；今天讲业务平台，不讲交付运维」 |
| 2–4 | `/demo` | 故事导航 · WorkOrder 条数 · 诚实后置条 |
| 4–6 | `/data` | **确保演示种子** 后指 Dataset/Build/DLQ；可链深页 |
| 6–9 | `/ontology` → Funnel | 实例/邻居 + hub 链到 `/ontology/funnel` |
| 9–12 | `/demo` → **一键写回** · `/aip/drafts` | Draft→批准→`wo-1001.status` 变 → 谱系 id |
| 12–14 | `/workshop/canvas` | Filter+Object Table **预览运行态** |
| 14–16 | `/workshop/buddy` | 绑 wo-1001 上下文问一句风险 |
| 16–18 | `/demo` → **治理探针** | 脱敏 `internalCost` · Marking FORBIDDEN · 最近谱系 |
| 18–19 | `/demo` → Capability 一镜（可选） | Job→MediaSet · CSV 解析 · OCR probe 诚实 |  
| 18–20 | 收束 | 「本地可装可演示；Apollo 气隙/Full 与 Notebook 分析另排期」 |

## 2. 故障回退

| 现象 | 处理 |
| --- | --- |
| health 红 | `scripts\demo\health-check.ps1`；重跑 `start-local.ps1` |
| 无对象 | `/demo` → 确保种子；或 `POST /v1/demo/ensure-seed` |
| Buddy 慢/空 | 说明 Facade + mock/边车；不现场调外网模型 |
| 客户问 Jupyter | 「产品 1.3 显式后置；今天演示运营写回」 |

## 3. 收尾

```powershell
powershell -File scripts\demo\stop-local.ps1
# 需要连 Docker 一起停：
# powershell -File scripts\demo\stop-local.ps1 -AlsoInfra
```
