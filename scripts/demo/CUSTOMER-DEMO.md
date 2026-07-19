# 客户彩排脚本（TB.8）· 15～20 分钟

> **对齐**：[78](../../../docs/palantier/20_tech/78-蓝图页面对齐差距台账与去演示Hub方案.md) · [110](../../../docs/palantier/20_tech/110-W33-可演示冻结维护Runbook方案.md) · [103](../../../docs/palantier/20_tech/103-W26-DataPage-Sync-Pipeline跳转链方案.md) · [104](../../../docs/palantier/20_tech/104-W27-彩排L1链路与ensure-seed同步Sync方案.md)  
> **故事**：WorkOrder 工单运营 · **本地 Docker**  
> **原则**：**只走真实功能页**（无 `/demo` Hub · 概览无业务主链区块）  
> **不讲**：Full Spoke / Helm / 现场 Ferry / 生产 IdP / 真 Jupyter·nbclient / Apollo 运维深水  
> **可讲（TA.7）**：`/analytics` 演示一镜（读数→Draft→批准→谱系）；日常写回仍走审批台

## 0. 开场前（你这边 · 2 分钟）

**macOS / Linux：**

```bash
cd aos-platform
bash scripts/demo/start-local.sh
bash scripts/demo/run-freeze-check.sh        # 快检（demo + npm 19）· 见 110
bash scripts/demo/run-rehearsal-smoke.sh     # 彩排：demo + Agnes（.env 已配时）
```

**Windows：**

```powershell
cd c:\work\projects\wchat\aos-platform
powershell -File scripts\demo\start-local.ps1
powershell -File scripts\demo\run-freeze-check.ps1
powershell -File scripts\demo\run-demo-smoke.ps1   # 或仅 demo smoke
```

打开 http://127.0.0.1:5173/ · `/data` → **初始化业务数据**

## 1. 演示顺序（对着客户）

| 分钟 | 页面 | 话术要点 |
| --- | --- | --- |
| 0–2 | `/` 概览 | 「AI 操作系统控制面 · 四域入口 · 不讲 Apollo 运维」 |
| 2–5 | `/data` | **初始化业务数据** → Hub 四域指标 · **L1 链路态**：② Sync 列表 → 行内 **Pipeline →** · Source **详情** 看关联 Pipeline · ③ 进 **管道构建** |
| 5–7 | `/ontology` → Funnel | 实例/邻居 + Funnel 映射状态 |
| 7–10 | `/aip/drafts` → **一键写回闭环** | Draft→批准→`wo-1001.status` 变 → 谱系 id |
| 10–12 | `/workshop/inbox` | Filter+Table+Object View · 选中 `wo-1001` |
| 12–14 | `/workshop/graph` → `@Buddy` | 图谱 1-hop · 带 order 进 Buddy |
| 14–16 | `/workshop/buddy?order=wo-1001` | 与 Inbox 同源工单表 · Agnes 真答（已配 .env） |
| 16–18 | `/aip/studio` 或 `/aip/logic` | Studio 试对话 / Logic Use LLM 块（可选） |
| 16–18 | `/aip/lineage` → **治理探针** | 脱敏 `internalCost` · Marking FORBIDDEN |
| 18–19 | `/aip/capabilities` → **业务一镜**（可选） | Job→MediaSet · CSV 解析 |
| 19–21 | `/analytics` | 产品面：读数 → 提交 Draft → 审批台；分组/时序/实验 |
| 21–22 | API（彩排） | `POST /v1/demo/run-analytics-story`（**不**在产品页点；仅脚本/冒烟） |
| 22–23 | 收束 | 「分析建模 MVP；Apollo Full / 真 Jupyter / BI·ML 全集另排期」 |

## 2. 故障回退

| 现象 | 处理 |
| --- | --- |
| health 红 | `bash scripts/demo/health-check.sh` 或 `start-local` 重跑 |
| 无对象 | `/data` → 初始化业务数据；或 `POST /v1/demo/ensure-seed` |
| Buddy/Studio 仍 mock | `.env` 填 `AGNES_*` 后 `bash scripts/demo/ensure-api.sh --restart` |
| API 掉线 · Failed to fetch | `bash scripts/demo/ensure-api.sh` |
| 客户问 Jupyter | 「MVP 是 shaped 边车+Facade；真 Jupyter/nbclient 另排；今天看演示一镜写回」 |
| 演示一镜失败 | `POST /v1/demo/ensure-seed` 后重点；或 `POST /v1/demo/run-analytics-story` |

## 3. 收尾

```bash
bash scripts/demo/stop-local.sh
# 需要连 Docker 一起停：见 scripts/demo/README.md
```

```powershell
powershell -File scripts\demo\stop-local.ps1
```
