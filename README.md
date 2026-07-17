# aos-platform（自有仓 · 业务平台可演示）

对齐：`docs/palantier/20_tech/26` §12 · [70 业务演示优先](../docs/palantier/20_tech/70-业务平台可演示优先计划.md) · 活记录 [`27`](../docs/palantier/20_tech/27-本机开发基础设施与工程门禁记录.md)

## 10 分钟演示路径（TB.0 · 推荐）

```powershell
cd c:\work\projects\wchat\aos-platform
powershell -File scripts\demo\start-local.ps1
```

详见 [`scripts/demo/README.md`](scripts/demo/README.md)。成功标志：`RESULT: DEMO HEALTH OK`  
Web http://127.0.0.1:5173/ · API http://127.0.0.1:8080/v1/health · `Bearer dev`

## 目录

```text
apps/web                 React 18 + Vite
services/aos-api         FastAPI 契约面
packages/contracts       OpenAPI
deploy/dev               本机 PG + MinIO（禁止进客户包）
scripts/demo             TB.0 一键启动 / 健康检查
scripts/ci               军规扫描
```

## 1. Dev 前置（G5 · 手工）

```powershell
cd c:\work\projects\wchat\aos-platform
docker compose -f deploy/dev/docker-compose.yml up -d
```

- PostgreSQL: `127.0.0.1:5433` / db `aos_meta` / user `aos_app`
- MinIO API: `http://127.0.0.1:9000` · Console `:9001`
- 口令见 `deploy/dev/.secrets.env`（仅本地）

## 2. 启动 aos-api（G1/G4 · 手工）

```powershell
cd services\aos-api
pip install -e .
$env:AOS_LOG_LEVEL = "debug"
$env:AOS_LOG_FORMAT = "json"
uvicorn aos_api.main:app --host 127.0.0.1 --port 8080
```

探活：`GET http://127.0.0.1:8080/v1/health`

## 3. 启动 Web（G1 · 手工）

```powershell
cd apps\web
npm install
npm run build
npm run dev
```

## 4. 军规扫描（G3）

```powershell
# 应 PASS（排除 fixtures）
powershell -File scripts\ci\check-no-upstream-sdk.ps1

# 应 PASS（fixtures 故意违规）
powershell -File scripts\ci\check-no-upstream-sdk.ps1 -ExpectFail
```

## 军规

- UI **只**调 aos-api（23 R-ARCH-01）
- `deploy/dev` 与 MinIO **不进**客户交付包（23 R-LIC-01）
- Apollo 运维加深后置；业务演示主路径见 26 §12 TB.*
