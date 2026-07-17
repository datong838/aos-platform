# TB.0 · 本地演示 10 分钟路径

> **对齐**：[70](../../../docs/palantier/20_tech/70-业务平台可演示优先计划.md) · [26 §12](../../../docs/palantier/20_tech/26-AOS目标态开发计划.md) · **[72 启停手册](../../../docs/palantier/20_tech/72-系统启停与健康检查手册.md)**  
> **目标**：本机 Docker + API + Web，**不依赖** Apollo Full / 客户 IdP / 现场 Ferry。

## 前置

- Docker Desktop 已开  
- Python 3.11+ · Node 18+ · 本仓 `aos-platform/`

## 一键启动（推荐）

```powershell
cd c:\work\projects\wchat\aos-platform
powershell -File scripts\demo\start-local.ps1
```

成功标志：`RESULT: DEMO HEALTH OK`

| 入口 | URL |
| --- | --- |
| **客户演示导航** | http://127.0.0.1:5173/demo |
| Web 概览 | http://127.0.0.1:5173/ |
| API 探活 | http://127.0.0.1:8080/v1/health |
| 鉴权（演示） | `Authorization: Bearer dev`（`AOS_AUTH_ALLOW_DEV=1`） |

## 演示冒烟 / 彩排

```powershell
powershell -File scripts\demo\ensure-seed.ps1
powershell -File scripts\demo\run-demo-smoke.ps1
# 话术：scripts/demo/CUSTOMER-DEMO.md
```

## 常用命令

```powershell
# 只起 Docker 前置
powershell -File scripts\demo\start-local.ps1 -InfraOnly

# 健康检查
powershell -File scripts\demo\health-check.ps1
powershell -File scripts\demo\health-check.ps1 -RequireWeb

# 停 API/Web（可选停 Docker）
powershell -File scripts\demo\stop-local.ps1
powershell -File scripts\demo\stop-local.ps1 -AlsoInfra
```

## 日志

- `deploy/dev/aos-api.out.log` / `aos-api.err.log`
- `deploy/dev/aos-web.out.log` / `aos-web.err.log`
- PID：`deploy/dev/demo-pids/*.pid`

## 诚实边界

- 本路径 = **业务平台演示基建**，不是 Full Spoke / 气隙 Ferry 运维包  
- 产品 1.3（Jupyter/R/SQL）仍后置（G-ALIGN-09）
