# W5c9r｜Pipelines 后置 GET 文档去重验证收口

1. 复习 231、W5c9l/m/n/p/q；静态核 `wave_ext.list_pipelines` 在前、`phase5_pipelines.list_pipelines` 在后，同路径 POST 仍重复且本波不改。
2. 文件级方案先提交 `m1@6f081bd8`。
3. 专项 RED `1 failed`：后置 GET 仍 `include_in_schema=True`，`--noconftest` 无 PG 夹具。
4. 只给 `phase5_pipelines.py` 后置 GET decorator 加 `include_in_schema=False`；endpoint、路径、注册顺序、鉴权、同路径 POST/详情/图/试跑均未改。
5. 专项 `1 passed, 14 warnings`；manifest 全套 + Dataset/Builds/Pipelines 文档累计 `12 passed, 2 subtests passed, 14 warnings in 39.35s`。py_compile/diff check 通过，test VM `aos_test_*` 残留 0。
6. 代码/方案复审：后置 GET 仍注册、前置 `wave_ext` 为 GET 文档权威；POST 仍在 OpenAPI，不调用任何 GET/POST handler。
7. 8080 业务浏览器离线、18181 旧进程未重载；不称线上/浏览器 GREEN。
8. verification/代码精确提交、D-waves/AOS CAS/Prime 更新。
9. 自动 W5c9s：先方案处理下一组 GET-only 文档冲突，POST/PUT 分派和真实原组 ACK/closure 不变。

230 L0 挂起、dev-org 零 canary、商城源不读、unknown 不重发/不手工 `run_definition`、m1 单写不 push。
