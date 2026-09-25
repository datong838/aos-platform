# W5c9s｜Schedules 列表 GET 文档去重验证收口

1. 复习 231、W5c9l/m/n/p/q/r；确认前置 `wave_ext.list_schedules`、后置 `phase5_schedules.list_schedules`，同路径 POST 与详情/run/pause 不在本波范围。
2. 文件级方案先提交 `m1@7b6ad222`。
3. 专项 RED `1 failed`：后置 GET 仍在 schema，`--noconftest` 无 PG 夹具。
4. 只给 `phase5_schedules.py` 后置 GET decorator 加 `include_in_schema=False`；不改 endpoint、路径、顺序、鉴权、POST 或 run/pause。
5. 专项 `1 passed, 13 warnings`；manifest 全套 + Dataset/Builds/Pipelines/Schedules 文档累计 `13 passed, 2 subtests passed, 13 warnings in 39.35s`。py_compile/diff check 通过，test VM `aos_test_*` 残留 0。
6. 方案/代码一致性：后置 GET 仍注册，前置 GET 的 OpenAPI tags 对应可达权威，POST/pause 文档仍保留；无 handler 调用。
7. 8080 业务浏览器离线、18181 旧进程未重载，不能称线上/浏览器 GREEN。
8. verification/代码精确提交、D-waves/AOS CAS/Prime 更新。
9. 自动 W5c9t：先方案评估剩余 ontology GET-only 文档冲突及其 POST/PUT 同形关系，不因文档去重激活写路由；真实原组 ACK/closure 冻结。

230 L0 挂起、dev-org 零 canary、商城源不读、unknown 不重发/不手工 `run_definition`、m1 单写不 push。
