# Production PreparationWorker 可信装配方案

日期：2026-09-12

## 目标

建立一个由宿主独占构造的正式 preparation 依赖闭包，并按 exact `TenantScope` 生成未启动的
`LiveInstallationScheduler`。该 scheduler 只能组合持久 runtime connector、当前签名 Registry release/制品
reader、schema conditions、apply/verify/enable 三种当前权限、四来源配置授权、完整 OCI driver 与 control
plane 唯一 live job directory。

## 军规

1. `ProductionPreparationDependencies` 只接受 concrete production 类型；三种权限的 operation 必须分别为
   apply、verify、enable，OCI platform 只允许 `linux/arm64` 或 `linux/amd64`。
2. connector、store、revalidator、policy、loader、configuration authorization、driver 与 live directory 都由
   server wiring 注入；租户请求不能替换任何一项。revalidator 必须持有同一个 policy，loader 必须持有该
   policy 的同一 trust-root provider，四来源授权内部 permission 必须持有同一个 installation store。
3. `build_scheduler(scope)` 每次固定同一 TenantScope，创建 `CurrentRuntimeReleaseArtifacts`、
   `CurrentSchemaConditions`、`PreparationWorker`、pending directory 与 owner factory；同一个依赖闭包复用
   control plane 唯一 live directory。
4. worker 的 record 与 member artifact reader 必须来自同一个 exact tenant reader；legacy 无 member reader
   入口使用固定 fail-closed 函数，不能绕过 selected release identity。
5. 构造只建立对象，不连接数据库、不读取制品、不探测或启动 OCI、不 claim/ACK、不登记 live job。
   `ManifestLoader` 的 allowlist 根 identity 已由上游构造时固定，不在 tenant factory 中重建。
6. 本波不修改 production selector/assignment，因此即使环境变量完整也不会启动 preparation；下一波在三平面
   identity preflight 通过后才把 scheduler 接入 assignment。

## 修改目录

- `services/aos-api/aos_api/extension_runtime/production_preparation.py`
- `services/aos-api/tests/extension_runtime/test_production_preparation.py`
- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/`
- `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/closure-manifest.md`

## 退出条件与下一波

exact 类型/operation/platform 反证、同租户 reader/conditions/worker/scheduler 闭包、跨租户隔离、零 connector、
零 artifact、零 OCI 构造副作用均通过；邻接 runtime 回归、hash、closure 和独立提交完成。下一波把此闭包
接入 production host selection，在 identity preflight 后为每个 typed assignment 构造 same-scope scheduler。
