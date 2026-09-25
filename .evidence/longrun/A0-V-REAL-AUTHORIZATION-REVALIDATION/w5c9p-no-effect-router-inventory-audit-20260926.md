# W5c9p｜路由 inventory 与 lifespan 探针外部效果隔离审计

方案 `m1@05e30c5e`。旧 `RUNTIME_PROBE` 在同一子进程先生成 schema、再两次 `main.lifespan(app)`；静态审出即使 Host/Cron/snapshot flags 关闭，lifespan 仍构造控制平面、取得 registration connector、运行兼容 wiki/memory 冷启动、Host 选择、Provider 维护选择和 shutdown。只设环境变量不足以证明无 DB/Worker/源效果。

本波只改 `services/aos-api/tests/test_domain_router_manifest.py`：子进程按精确 `AOS_ROUTER_PROBE_MODE` 分支。`inventory` 在 app import/schema 摘要后立即落盘并退出，**不进入 lifespan**。`boundary` 在首次 lifespan 前给 control plane、registration connection、wiki/memory 冷启动、pipeline/JDBC warmup、Cron/logic、Provider/Host selection、snapshot worker、shutdown 全部装入无效果替身；仍保留原 `managed` 跳过 `init_schema` 与迁移失败原样传播两个断言。未知 mode 抛错，不能悄悄运行 boundary。只给 `boundary` 命名为 stubbed ports，不宣称生产环境无副作用。

旧封印 4479/旧 sha256/2680 在加替身后安全 RED 于 4511；独立无 lifespan inventory 计算出 4511、sha256 `3ce493dbdcb5cc3069d515983399b336187d1eda400f8e9a0a5c6bec773c0c0d`、paths 2710、十组重复。更新固定常量，不把摘要断言写成动态自等式。m1 当前 app 仍有 W5c9n 后置 Dataset GET schema 隐藏；若路由新增/改动，下次仍会红。

运行全局 pytest `--noconftest`，没有自动 PG 夹具；专用 test VM `aos_test_*` 残留 0、18181 旧进程不变、8080 离线。该测试只验证 fixture 隔离后的边界，不是自然运行、浏览器或真实授权验收。
