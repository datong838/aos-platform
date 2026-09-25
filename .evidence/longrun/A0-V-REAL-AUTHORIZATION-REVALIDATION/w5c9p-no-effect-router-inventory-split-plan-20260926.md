# W5c9p｜路由纯 inventory 与 lifespan 边界测试拆分方案

## 上位与目的

W5c9o `m1@c3194653`/AOS-000703 修正三项 manifest 静态封印；旧 `test_runtime_routes_match_pre_manifest_baseline` 同时生成路由摘要和两次进入 `main.lifespan(app)`，不能为纠正 4479/hash/2680 而无视真实 DB/后台门。231 的测试/安全军规要求可重现、无外部副作用及不冒充真实 GREEN。

## 文件级清单与停止条件

- 只读审 `services/aos-api/tests/test_domain_router_manifest.py` 的 `RUNTIME_PROBE`、`services/aos-api/aos_api/main.py` lifespan 全路径、当前依赖库 lazy router。列出 startup 可能发生的 DB/worker/源/Provider 行为，即使外层设置 Host=0/Cron=false 也不默认安全。
- 在 `test_domain_router_manifest.py` 中将现有 probe 拆成**纯路由 inventory**和独立 lifespan probe：前者只 import app、展开 route、算精确 count/hash/paths/duplicates，绝不进入 lifespan；后者保留原迁移失败传播/managed 跳过 bootstrap 断言，但必须提供足够的 mock/隔离使其无 DB/worker/源后才可运行。不得用 skip 或删除断言伪绿。
- 先针对纯 inventory 写 RED，使用 W5c9o 离线候选 4511/hash `3ce493db...`/paths2710，但必须用独立新 probe 重算并核一致后才能更新冻结值。若 lifespan 安全边界无法在本波证明，暂停其执行并在 verification 保留未验，不强行跑全测。
- 所有 pytest `--noconftest`，显式禁后台 flags；不绑定端口、不读商城源/真实 PG、不触发 handler。专项/累计和代码/方案一致性复审；8080 离线。

## 九步

1. 复习 231、W5c9o 与原 probe 的安全边界。
2. 方案先提交。
3. 静态列出 lifespan 外部效果与 mock 入口。
4. 最小测试拆分，RED→GREEN；未知则停止。
5. 纯 inventory 专项 + 已安全的静态累计。
6. 不删除生命周期断言、不把未运行写 GREEN。
7. 8080 业务浏览器离线。
8. audit/verification、精确提交、D-waves/AOS CAS/Prime。
9. 自动下一波补足生命周期安全验证或下一组路由文档切片；原组 ACK/closure 冻结。

230 L0 挂起、dev-org 零 canary、商城源不读、unknown 不重发/不手工 `run_definition`、m1 单写不 push。
