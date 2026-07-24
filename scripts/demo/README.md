# TB.0 · 本地演示 10 分钟路径

> **对齐**：[70](../../../docs/palantier/20_tech/70-业务平台可演示优先计划.md) · [26 §12](../../../docs/palantier/20_tech/26-AOS目标态开发计划.md) · **[72 启停手册 v1.6](../../../docs/palantier/20_tech/72-系统启停与健康检查手册.md)**（**四版 SOP**：单机/标准企业/集团/SaaS）· [98 W21](../../../docs/palantier/20_tech/98-W21-演示脚本README与72手册对齐方案.md)  
> **目标**：本机 Docker + API + Web = **① 单机版**路径；**不依赖** 集团真舰队 / 客户 IdP / 现场 Ferry。

## 分轨（Windows / macOS / Linux）

| OS | 启动 | 说明 |
| --- | --- | --- |
| **Windows** | `*.ps1` | **既有真源**；打包/CI 仍用 `scripts/ci/*.ps1`，本 Mac 改动**不触及** |
| **macOS** | `*.sh` | 并列新增；Hub 不通用 `start-local-native.sh` |
| **Linux** | `*.sh` | 与 mac 同族；打包清单另开，不改 Win |

安装前置、本机启动、客户包/Ferry 打包三者均可按 OS 分开维护（见 [24 §4.1](../../../docs/palantier/20_tech/24-AOS客户侧前置组件安装SOP.md)）。

## 前置

- Docker Desktop 已开（或见 [24 §4.4](../../../docs/palantier/20_tech/24-AOS客户侧前置组件安装SOP.md) 原生降级）  
- Python 3.11+ · Node 18+ · 本仓 `aos-platform/`

## Agnes / LLM（可选 · Dev）

在 `aos-platform/.env` 填写（**勿提交 Git**）：

```text
AGNES_API_KEY=...
AGNES_BASE_URL=https://apihub.agnes-ai.com/v1
AGNES_TEXT_MODEL=agnes-2.0-flash
AGNES_IMAGE_MODEL=agnes-image-2.1-flash
```

改 `.env` 后须重载 API：

```bash
bash scripts/demo/ensure-api.sh --restart
```

详见 [94](../../../docs/palantier/20_tech/94-W17-Agnes默认接入与LLM回归方案.md)。

## 一键启动（推荐）

**Windows（不变）：**

```powershell
cd c:\work\projects\wchat\aos-platform
powershell -File scripts\demo\start-local.ps1
```

**macOS / Linux：**

```bash
cd ~/work/projects/ai_agent/aos-platform   # 按本机路径
bash scripts/demo/start-local.sh
# Docker Hub 不可达时：
bash scripts/demo/start-local-native.sh
```

成功标志：`RESULT: DEMO HEALTH OK`

| 入口 | URL |
| --- | --- |
| **Web 概览** | http://127.0.0.1:5173/ |
| 数据连接 / 种子 | http://127.0.0.1:5173/data |
| Draft 审批 | http://127.0.0.1:5173/aip/drafts |
| API 探活 | http://127.0.0.1:8080/v1/health |
| 鉴权（演示） | `Authorization: Bearer dev`（`AOS_AUTH_ALLOW_DEV=1`） |

## 演示冒烟 / 彩排

**Windows：**

```powershell
powershell -File scripts\demo\ensure-seed.ps1
powershell -File scripts\demo\run-demo-smoke.ps1    # 含 l1-chain（W36）
powershell -File scripts\demo\run-freeze-check.ps1  # demo + npm test（W36）
```

**macOS / Linux：**

```bash
bash scripts/demo/ensure-seed.sh
bash scripts/demo/run-demo-smoke.sh    # 含 l1-chain（Source/Sync/Pipeline 同 sourceId · W27）
# TB.8 彩排（demo + Agnes，.env 已配时）：
bash scripts/demo/run-rehearsal-smoke.sh
# 仅 Agnes 真 LLM 回归：
bash scripts/demo/run-agnes-smoke.sh
```

话术：`scripts/demo/CUSTOMER-DEMO.md`

## 冻结维护（W33 · cosmetic 已清零）

UI **编码默认冻结** · 日常快检：

```bash
bash scripts/demo/run-freeze-check.sh          # demo smoke + npm test（19）
bash scripts/demo/run-freeze-check.sh --full   # + pytest + rehearsal
```

详见 [110](../../../docs/palantier/20_tech/110-W33-可演示冻结维护Runbook方案.md) · [109 W32 cosmetic 收口](../../../docs/palantier/20_tech/109-W32-门禁台账W29-W31证据回写与cosmetic收口方案.md)

## 工程回归（Agent / CI）

```bash
bash scripts/demo/run-freeze-check.sh    # 快检 · 改 Web 后
bash scripts/ci/run-pytest.sh            # aos-api · 180+ passed
cd apps/web && npm test                  # 19 passed
bash scripts/demo/run-rehearsal-smoke.sh # 彩排前 · 含 Agnes
```

## 常用命令

**Windows：**

```powershell
powershell -File scripts\demo\start-local.ps1 -InfraOnly
powershell -File scripts\demo\health-check.ps1
powershell -File scripts\demo\health-check.ps1 -RequireWeb
powershell -File scripts\demo\stop-local.ps1
powershell -File scripts\demo\stop-local.ps1 -AlsoInfra
```

**macOS / Linux：**

```bash
bash scripts/demo/health-check.sh
bash scripts/demo/health-check.sh --require-web
bash scripts/demo/ensure-api.sh              # API 掉线时单独拉起
bash scripts/demo/ensure-api.sh --restart    # 改 .env 后重载 AGNES_*
bash scripts/demo/stop-local.sh
```

## 日志

- `deploy/dev/aos-api.out.log` / `aos-api.err.log`
- `deploy/dev/aos-web.out.log` / `aos-web.err.log`
- PID：`deploy/dev/demo-pids/*.pid`

## 诚实边界

- 本路径 = **业务平台演示基建**，不是 Full Spoke / 气隙 Ferry 运维包  
- 产品 1.3（Jupyter/R/SQL）仍后置（G-ALIGN-09）  
- Web 无 `/demo` Hub · 概览 `/` 四域 live 指标（见 [97](../../../docs/palantier/20_tech/97-W20-概览四域Live指标与控制面加深方案.md)）
