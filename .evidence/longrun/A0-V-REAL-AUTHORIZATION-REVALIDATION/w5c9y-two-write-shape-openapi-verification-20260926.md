# W5c9y｜两组写方法参数形状文档权威验证

1. 复习 231/230 L0、W5c9w matcher 与 W5c9x GET 切片；限定 Ontology detail PUT、Schedules run POST 文档，真实写动作未获新授权。
2. 文件级方案先提交 `m1@0b91cbc7`，累计封印与旧断言差异补证 `m1@dde1d780`、`m1@17909c9a`，均在对应测试调整前。
3. endpoint-free RED：两组后置写文档仍 included（2 failed），独立文档检查 1 passed；`--noconftest` 无数据库夹具、无 HTTP 写请求。
4. 只给 `phase4_ontology_types.py` 的后置 PUT、`phase5_schedules.py` 的后置 POST run decorator 加 `include_in_schema=False`。未更改函数体、路由顺序/路径/鉴权、任何前置可达写 handler。
5. 专项 3 passed；累计先因后置写文档旧断言与路径封印得到 26 passed/3 failed，补三项后仍有同一旧测试的后置 POST 断言，最终完整累计 `29 passed, 2 subtests passed, 7 warnings in 39.84s`。OpenAPI 路径 2708→2706：后置 `{ot_id}` 与 `{sc_id}/run` 两键不再有公开方法；前置 PUT/POST 与独立 pause 保留。真实 route 4511 与既有哈希未变。`py_compile`、`git diff --check` 通过，测试 VM `aos_test_*` 残留 0。
6. endpoint-free matcher 锁两组代表 scope 仍前、后双 FULL，先者 included、后者 excluded；方案/代码一致，未发 PUT/POST，也未调用 handler。特别未触发真实 live pipeline。
7. 8080 无监听，18181 仍 PID 28077 旧进程且未重载；不称业务浏览器/线上验收 GREEN。
8. 本 verification/代码精确提交，D-waves/AOS CAS/Prime 同步；原十二 Run row proof/Fleet/Owner/ACK/closure 仍无权威。
9. 下一波 W5c9z 先只读复盘剩余 OpenAPI 可达性与运行时部署门禁，再决定安全的最小测试/修复切片；不能因为文档测试 GREEN 就启动或重放原 A0-V。

230 L0 挂起、dev-org 零 canary、商城源不读、unknown 不重发/不手工 `run_definition`、m1 单写不 push。
