# 开发、测试与部署

## 1. 本机环境

- Python 3.11+
- Node.js 20 与根 `package.json` 固定的 pnpm
- Docker（用于 `deploy/dev` 的 PostgreSQL / MinIO）
- Helm 3（仅验证 Full Spoke chart 时需要）

依赖安装与本机启动详见根 [README](../README.md) 和 [演示说明](../scripts/demo/README.md)。质量门本身不会静默安装依赖。

## 2. 分级验证

```bash
bash scripts/ci.sh quick  # 入口与 shell 自检
bash scripts/ci.sh wave   # OpenAPI、后端、客户端、Helm、源码安全门
bash scripts/ci.sh full   # wave + 生产构建 + 产物安全扫描
```

修改公共契约、工作区、CSS/导航或部署模板时，先跑对应专项门；每个合并阶段再跑 `wave`，最终合并跑 `full`。

## 3. Full Spoke Helm 静态参考

Chart 位于 `deploy/spoke-full/chart`，默认不创建 Ingress/PVC，不保存明文凭据。运行：

```bash
bash scripts/ci/helm-template-spoke-full.sh --require
```

该命令执行 schema 校验、lint、默认配置与 production-like 配置的重复渲染、确定性比较及基础安全断言。它不会连接 Kubernetes，也不会创建 Secret、PVC 或其他外部资源。

部署前必须在目标命名空间预先创建 Secret，并只在 values 中提供 Secret 名称和 key 名：

```yaml
existingSecret:
  name: aos-spoke-runtime
  hubTokenKey: hub-token
```

生产环境还应显式覆盖镜像仓库与不可变 tag、Hub HTTPS 地址、Spoke ID、Ingress/TLS、资源、存储和调度约束。真实安装、连通性、升级回滚、容量和 SLO 不在本静态门的验收范围内。
