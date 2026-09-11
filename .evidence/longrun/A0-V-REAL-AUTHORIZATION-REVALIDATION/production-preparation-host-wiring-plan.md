# Production preparation host wiring 方案

日期：2026-09-12

## 目标

把 9.38 的可信 preparation 依赖闭包接入正式 runtime host assignment。只有 runtime host 已显式启用、
全部连接与 OCI/platform 配置完整、directory/runtime/web 三平面数据库身份隔离预检通过之后，才按数据库
返回的 exact TenantScope 构造 `LiveInstallationScheduler` 并放入 `RuntimeTenantAssignment.lifecycle`。

## 军规

1. `RuntimeWorkerDependencies` 新增 exact `ProductionPreparationDependencies`；它必须复用同一个
   Installation store、四来源 configuration authorization，并与 cleanup facade 使用同一 OCI context。
2. selector 要求 preparation connector 与刚完成身份验证的 runtime connector 是同一对象，防止预检一个
   principal、执行另一个 principal。
3. `build_production_runtime_host_selection` 只有在 host flag、runtime/directory DSN、OCI context 和
   `AOS_EXTENSION_RUNTIME_PLATFORM` 全部存在时才构造依赖；platform 只允许 `linux/arm64`、
   `linux/amd64`。缺失或非法固定返回 inactive，不连接数据库、不读取 allowlist root。
4. production wiring 只创建一次 trust-root provider、ReleasePolicy、ManifestLoader 和 OciDriver；runtime
   revalidator、artifact/schema reader、preparation/cleanup 均来自这一依赖图。
5. `build_assignment` 仅由已验证的 directory descriptor 调用；scheduler scope 必须与 assignment scope
   exact 相等，既有 host replacement/removal/stop cleanup 负责其生命周期收敛。
6. 本波只完成宿主装配与预检，不主动启动 app/host，不创建 1.5.0、不消费真实 outbox、不改变租户数据。

## 修改目录

- `services/aos-api/aos_api/asset_registry/control_wiring.py`
- `services/aos-api/aos_api/extension_runtime/production_runtime.py`
- `services/aos-api/tests/extension_runtime/test_production_runtime.py`
- `services/aos-api/tests/extension_runtime/test_runtime_host_directory_pg.py`
- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/`
- `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/closure-manifest.md`

## 退出条件与下一波

缺配置/错 platform/错 connector/混搭 store-authority/错 OCI context 均在连接或 worker 构造前拒绝；完整
配置在三平面 identity 通过后产生 same-scope lifecycle，目录 cache、replacement/stop 与真实 PG identity
回归通过；hash、closure 和独立提交完成。下一波验证 app lifespan 真实启动/停止路径和 host tick 的
preparation 路由，但仍以无 pending apply 的隔离租户证明零 OCI/零租户变化。
