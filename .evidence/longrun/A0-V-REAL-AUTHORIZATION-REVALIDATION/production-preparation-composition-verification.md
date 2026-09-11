# Production PreparationWorker 可信装配验证

日期：2026-09-12

## 结论

新增 `ProductionPreparationDependencies`。它只接受同步 runtime connector、PostgreSQL Installation store、
同一 ReleasePolicy 的 runtime revalidator、同 trust-root provider 的 ManifestLoader、apply/verify/enable 三种
exact 当前权限、同 store 的四来源配置授权、完整 OciDriver、显式 Linux platform 与 control plane 唯一
live directory。

`build_scheduler(scope)` 按 exact TenantScope 组合同一个 `CurrentRuntimeReleaseArtifacts` 实例的 record/member
artifact reader、`CurrentSchemaConditions`、`PreparationWorker`、pending directory、owner factory 与 scheduler。
legacy 无 selected-release artifact reader 固定拒绝。构造后 owners 为空，未读取数据库/制品，未调用 OCI。

## 实测

- 新增 composition 合同：16 passed。
- runtime release reader、pending directory、scheduler、owner、host、production selector 邻接回归：87 passed。
- preparation worker 与 schema conditions：16 passed。
- preparation consumer、schema conditions、pending directory 隔离 PostgreSQL 回归：21 passed。
- `py_compile`、`git diff --check` 通过。
- AR2-7 closure validator 通过：1786 个 Python 模块扫描、155 个分类模块、93 个迁移模块，hash、正反向依赖、
  bundle 跨层引用和动态引用错误均为 0。

覆盖 exact 类型、同步 connector、三种 permission operation 不可串换、platform allowlist、policy/revalidator、
policy/loader trust roots、configuration/store 同源、同租户对象闭包、跨租户 Worker 隔离、共享唯一 live
directory，以及零 connector/制品/OCI 构造副作用。7 条既有框架 warning 与 pytest 退出时既有 JDBC 日志流
关闭提示不改变 exit code 0。

## 方案一致性与风险

- 实现与方案一致：租户不能注入 record、artifact、permission、configuration authority、driver 或 platform。
- 本波仍未接 production selector/assignment，所以不会消费真实 runtime-apply，也不会改变 1.4.0 或租户数据。
- ManifestLoader 在上游构造时会固定 allowlist 根 identity；tenant factory 本身不触碰文件系统。
- 真实 signed release、OCI session 与完整 apply→verify→enable 联合演练仍依赖下一波 production wiring 和随后
  1.5.0 candidate/install。

## 下一波

扩展 `RuntimeWorkerDependencies` 持有 exact preparation 闭包；仅在 directory/runtime/web 三平面 identity
preflight 全部通过后，为每个 typed assignment 调用 `build_scheduler(scope)` 并注入 lifecycle。补充环境显式
platform 门、零前置构造反证、same-scope assignment 与 replacement/stop cleanup 回归。
