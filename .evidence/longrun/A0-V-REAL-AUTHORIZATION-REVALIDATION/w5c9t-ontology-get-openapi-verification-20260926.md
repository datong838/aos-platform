# W5c9t｜Ontology 三个后置 GET 文档去重验证收口

1. 复习 231、W5c9l/m/n/p/q/r/s；静态确认前置 `ontology` 与后置 phase4 的三个精确 GET 冲突，POST branches/PUT object-types 另有写路径风险。
2. 文件级方案先提交 `m1@8ed95031`。
3. 新测试 RED：三个后置 GET 均仍公开（3 failed），写路由/独立 phase4 文档保留检查 1 passed；`--noconftest` 无 PG 夹具。
4. 只给 `phase4_ontology_branches.py` 的 branches/graph-health GET 和 `phase4_ontology_types.py` 的 object-types GET decorator 加 `include_in_schema=False`；不改 handler、顺序、鉴权、POST/PUT 或其它路由。
5. 专项 4 passed、10 warnings；manifest 全套 + Dataset/Builds/Pipelines/Schedules/Ontology 文档累计 `17 passed, 2 subtests passed, 10 warnings in 39.20s`。py_compile/diff check 通过，test VM `aos_test_*` 残留 0。
6. 方案/代码一致性：前置 `ontology` 三 GET 为文档权威、后置三个 route 仍注册；POST branches、PUT object-types 和独立 `/recent` 文档仍有，未调用 handler。
7. 8080 业务浏览器离线，18181 旧进程未重载；不能称线上/浏览器 GREEN。
8. verification/代码精确提交、D-waves/AOS CAS/Prime 更新。
9. 自动 W5c9u：先方案审余下精确 POST 与参数形状重复的 no-activation 文档门，不能让后置写 endpoint 变可达；真实原组 ACK/closure 冻结。

230 L0 挂起、dev-org 零 canary、商城源不读、unknown 不重发/不手工 `run_definition`、m1 单写不 push。
