# AOS Platform 架构与边界

## 1. 分层

```text
Web / Desktop
      |
      v
   AOS API  <---- Ontology SDK / OpenAPI contract
      |
      +---- platform domain services
      +---- plugin interfaces
      +---- persistence and external service adapters
```

- `apps/web` 与 `apps/desktop` 是两个客户端入口，共享平台 API 与 Ontology 语义，不直接绕过 API 访问服务端数据。
- `services/aos-api` 是契约、鉴权、领域编排和持久化边界。
- `packages/contracts` 保存可复核的 API 契约；`packages/ontology-sdk` 提供类型化客户端能力；`packages/ui-kit` 保存共享设计令牌。
- `plugins` 定义通用扩展接口。某个电商平台的认证、字段映射、限流和回调实现应在专项方案中落地，不写入通用核心。

## 2. 运行与交付边界

- `deploy/dev` 仅服务本机开发，不是客户交付物。
- `deploy/spoke-full/chart` 描述 Full Spoke 的 Kubernetes 静态参考包，只覆盖 lint、模板渲染和安全配置面。
- Hub/Spoke 的真实联机、集群安装、舰队控制、升级回滚和生产 SLO 必须另行验收；仓内 Helm 渲染通过不能替代这些证据。
- 凭据只通过环境注入或 Secret 引用进入运行时，禁止写入源码、values、模板产物和测试快照。

## 3. 变更原则

1. 先更新 `228-` 前缀技术方案，再修改实现。
2. 公共契约优先保持兼容；破坏性变更必须有显式迁移与回滚方案。
3. 每一波先跑专项测试，再跑统一回归；多阶段任务每阶段都必须保留通过证据。
4. 平台通用能力与具体渠道适配分离，避免把渠道假设固化到核心领域模型。

## 4. 关键验证入口

- 统一质量门：`bash scripts/ci.sh quick|wave|full`
- 敏感信息扫描：`bash scripts/ci/run-security-gate.sh --artifacts`
- Helm 静态门：`bash scripts/ci/helm-template-spoke-full.sh --require`
- API 测试：`services/aos-api/tests`
- 客户端测试：各 workspace 包的 `test`、`typecheck` 与 `build` 脚本
