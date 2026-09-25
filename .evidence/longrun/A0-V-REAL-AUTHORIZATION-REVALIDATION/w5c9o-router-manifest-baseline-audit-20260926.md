# W5c9o｜547→550 三项来源与残余封印审计

方案 `m1@d09c8515`。当前 `domain_manifest.json` 550 条，order 0–549 连续、(module,attribute) 550 唯一；生成器 `--check` 回 `OK router aggregate matches 550 manifest entries`。比旧静态测试 547 多的三项有独立 Git 来源：`9c87c6c8` 加 Data `pipeline_controls`；`70d01cae` 加 Infra `runtime_workshop` 并重编号后项；`ea88508f` 加 Infra `runtime_ui_resources`。当前域计数 Infra 27、Data 202，其它域与旧 `DOMAIN_COUNTS` 一致。生产 manifest/aggregates 未改；仅把静态冻结断言 547→550、Infra25→27、Data201→202，仍保留连续 order、域分布、唯一键和 generator 负例。

当前测试文件另有 runtime 封印 `count=4479`、旧 sha256 `656ad39e...`、OpenAPI paths 2680。该测试的子进程 `RUNTIME_PROBE` 会进入 `main.lifespan(app)` 两次，虽然 mock migration，但还构造运行控制平面；本波禁止碰真实 DB/运行任务，**未执行**它，不能称整套 manifest 测试全绿。独立不进 lifespan 的聚合在 W5c9n 文档改动后给出 count 4511（去 HEAD/OPTIONS）、sha256 `3ce493dbdcb5cc3069d515983399b336187d1eda400f8e9a0a5c6bec773c0c0d`、paths 2710、十组精确重复仍保留。该值是离线诊断，不直接替换 runtime test 封印，须下波先拆无副作用 inventory 与生命周期边界测试再核等价。

专用测试 VM `aos_test_*` 数据库残留仍 0。8080 业务浏览器离线；18181 旧进程未重载改动；A0-V 原组 no-authority 不变。
