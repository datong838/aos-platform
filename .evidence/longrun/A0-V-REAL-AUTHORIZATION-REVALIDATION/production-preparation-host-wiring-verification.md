# Production preparation host wiring 验证

日期：2026-09-12

## 结论

正式 runtime selector 现在持有完整 preparation 依赖闭包。host 未启用或 runtime/directory DSN、OCI context、
显式 runtime platform 任一缺失时不构造该闭包；platform 非 `linux/arm64`/`linux/amd64` 时固定 inactive。
完整配置只构造对象，三平面身份预检通过后才由 directory descriptor materialize exact TenantScope 的
assignment，并注入 same-scope `LiveInstallationScheduler`。

selector 额外要求 preparation connector 与接受身份验证的 runtime connector 为同一对象。
`RuntimeWorkerDependencies` 要求 preparation 与 configure/disable 复用同一个 Installation store、四来源授权，
且启动 driver 与 cleanup facade 指向同一 OCI context。

## 实测

- production wiring、preparation composition 与 runtime host 合同：55 passed。
- app startup、directory cache、host lifecycle、scheduler、pending 与 production 邻接回归：91 passed。
- 三平面数据库身份、assignment、expired attempt recovery 真实 PostgreSQL：11 passed。
- `py_compile`、`git diff --check` 通过。
- AR2-7 closure validator 通过：1786 个 Python 模块、156 个分类模块、93 个迁移模块；hash、正反向依赖、
  bundle 跨层引用和动态引用错误均为 0。

覆盖缺 platform 时零 allowlist access、非法 platform、runtime connector 混搭、三平面身份失败零 worker、
same-scope lifecycle、assignment revision cache，以及真实 runtime principal 下无 pending apply 的零 OCI tick。
7 条既有框架 warning 与 pytest 退出时既有 JDBC 日志流关闭提示不改变 exit code 0。

## 方案一致性与风险

- 实现符合预检顺序：directory identity → runtime/web identity → assignment/scheduler materialize。
- 生产 wiring 共用一份 trust roots、policy、loader、driver、store、configuration authority 和 live directory。
- 本波没有主动启动 app/host，没有 pending apply、OCI create、outbox ACK、1.5.0 或租户业务写入。
- 当前尚缺 app lifespan 在完整 production 配置下的真实启动/停止证据，也没有创建并安装 1.5.0 candidate。

## 下一波

补充完整配置下 app lifespan 持有 ACTIVE host、后台 tick、停止收敛的隔离测试；使用无 pending apply 的专用
租户证明启动后只读发现且零 OCI/零租户状态变化，并确认启动失败时 fail closed、不会留下 scheduler。
