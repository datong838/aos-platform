# W5c9o｜路由清单静态封印修正验证收口

1. 复习 231、W5c9n 与 manifest/generator 合同。
2. 方案先提交 `m1@d09c8515`。
3. Git 证实三项由 `9c87c6c8`、`70d01cae`、`ea88508f` 加入；当前 550/order0–549/键唯一/生成器一致。
4. RED 静态测试 `1 failed` 于 547≠550；只改 `test_domain_router_manifest.py` 的静态冻结数/Infra/Data 域计数，不动生产清单/路由。
5. 专项静态 2 passed；W5c9n 文档测试 + 全部七项 manifest 静态累计 8 passed、2 subtests passed、16 warnings。无 PG 全局夹具。旧 runtime probe 因会进 lifespan 未跑，不冒充全套 GREEN。
6. 方案/代码一致性：order/唯一键/域检查保留；离线路由摘要 4511/paths2710/十组重复仅作下波基线，旧 runtime hash 不盲改。
7. 8080 业务浏览器离线，18181 未重载。
8. audit/verification 精确提交，D-waves/AOS CAS/Prime 更新。
9. 自动 W5c9p：先方案拆分路由纯 inventory 与生命周期 probe，确保无副作用后修剩余 runtime 封印并回归；原组 ACK/closure 冻结。

230 L0 挂起、dev-org 零 canary、商城源不读、unknown 不重发/不手工 `run_definition`、m1 单写不 push。
