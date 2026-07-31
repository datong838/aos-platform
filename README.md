# AOS Platform

AOS Platform 是面向数据、Ontology 与 AI 应用的通用平台仓库。本仓库包含 FastAPI 服务、React Web、Tauri Desktop、Ontology SDK、插件接口和部署参考；具体电商平台连接器不属于当前通用平台交付范围。

## 仓库结构

```text
apps/web                  React Web
apps/desktop              Tauri Desktop
services/aos-api          FastAPI 服务与领域能力
packages/ontology-sdk     Ontology TypeScript SDK
packages/ui-kit           共享设计令牌
packages/contracts        OpenAPI 契约
plugins                   可扩展插件接口
deploy/dev                仅供本机开发的 PostgreSQL / MinIO
deploy/spoke-full/chart   Full Spoke Helm 静态交付参考
scripts/ci.sh             统一质量门入口
```

更完整的仓内说明：

- [架构与边界](docs/ARCHITECTURE.md)
- [外部设计文档桥接](docs/EXTERNAL_DESIGN.md)
- [开发、测试与部署](docs/DEPLOYMENT.md)
- [本机演示](scripts/demo/README.md)

## 本机开发

前置条件为 Python 3.11+、Node.js 20、pnpm（版本以根 `package.json` 为准）和 Docker。依赖安装完成后：

```bash
docker compose -f deploy/dev/docker-compose.yml up -d
cd services/aos-api && pip install -e '.[dev]'
cd ../.. && pnpm --filter @aos/web dev
```

默认地址：Web `http://127.0.0.1:5173/`，API 健康检查 `http://127.0.0.1:8080/v1/health`。`deploy/dev` 及其中的本机依赖不得进入客户交付包。

## 质量门

```bash
bash scripts/ci.sh quick
bash scripts/ci.sh wave
bash scripts/ci.sh full
```

质量门不会自动安装依赖。`wave` 包含 OpenAPI 确定性契约、后端、Web、Desktop、SDK、Helm 和源码安全门；`full` 额外包含生产构建与产物安全扫描。Helm 静态交付门也可单独执行：

```bash
bash scripts/ci/helm-template-spoke-full.sh --require
```

## 交付边界

- UI 仅通过 AOS API 访问平台能力。
- `deploy/spoke-full/chart` 是可 lint、可重复渲染的静态参考包，不代表已完成 Kubernetes 集群安装、远程发布或生产验收。
- Chart values 不承载 Token、密码、私钥和连接串正文，只引用已有 Kubernetes Secret。
- 外部 AGPL/BSL 服务端组件、本机 `deploy/dev` 依赖及具体电商适配不进入通用客户包。
