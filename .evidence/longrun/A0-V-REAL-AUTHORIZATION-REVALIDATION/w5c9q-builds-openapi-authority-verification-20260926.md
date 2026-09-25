# W5c9q｜Builds 后置 GET 文档去重验证收口

1. 复习 231、W5c9l/m/n/p 的路由分派与 no-effect 测试，确认 `wave_ext.list_builds` 在 `builds.list_builds` 前，后者唯一 GET `/v1/builds` 且其它 Build POST/DLQ/cancel 保留。
2. 文件级方案先提交 `m1@84b22400`。
3. 新测试 RED `1 failed` 于两个 route 的 `include_in_schema` 均 true，`--noconftest` 无 PG 夹具。
4. 只在 `services/aos-api/aos_api/routers/builds.py` 给后置 GET decorator 增 `include_in_schema=False`；endpoint/路径/注册顺序/鉴权/写路由均未改。
5. 专项 `1 passed, 15 warnings`；manifest 全套 + W5c9n Dataset + 本波 Builds 文档累计 `11 passed, 2 subtests passed, 15 warnings in 39.46s`。py_compile/diff check 通过，test VM `aos_test_*` 残留 0。
6. 方案/代码一致性：后置 GET 仍注册但不作为可达 OpenAPI；前置 wave_ext 为 GET 文档权威，其它 Build POST/DLQ/cancel 仍公开；无实际 handler 调用，不改变分派。
7. 8080 业务浏览器离线，18181 旧进程未重载新代码，不称线上/浏览器 GREEN。
8. verification/代码精确提交、D-waves/AOS CAS/Prime 更新。
9. 自动 W5c9r：先方案选择下一组 **GET-only** 文档冲突，继续保护后置写端点不被激活；原十二 Run ACK/closure 不变。

230 L0 挂起、dev-org 零 canary、商城源不读、unknown 不重发/不手工 `run_definition`、m1 单写不 push。
