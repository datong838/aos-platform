# W5c9x｜四组 GET 形状文档权威验证

1. 复习 231、230 L0 与 W5c9w 真实 matcher 审计，限定四组 GET；Ontology detail PUT、Schedules run POST 不动。
2. 精确方案先提交 `m1@43640b86`；累计路径封印差异的原因在改封印前补入方案 `m1@4b80e15f`。
3. endpoint-free 新测试 RED：四个目标参数形状各失败于 `[True, True]` 文档标记，独立 GET/PUT/POST 保留测试通过，即 `4 failed, 1 passed`；`--noconftest` 未加载 DB fixture。
4. 仅给 `phase3_aip_lineage.py`、`phase4_ontology_types.py`、`phase5_schedules.py` 的四个后置 GET decorator 加 `include_in_schema=False`；函数体、真实路由顺序、路径、鉴权及两个写方法未改。
5. 专项 5 passed；manifest 全套与 W5c9n/q/r/s/t/v 文档测试累计 `26 passed, 2 subtests passed, 7 warnings in 39.56s`。首次累计仅原 OpenAPI 路径数封印 2710 与实际 2708 不符（1 failed, 25 passed）；审明 GET-only AIP `{record_id}` 与 Schedules `{sc_id}/runs` 两键消失，Ontology `{ot_id}` 与 Schedules `{sc_id}` 保留 PUT，才精确改封印为 2708。业务 route 4511 与既有哈希未变。`py_compile`、`git diff --check` 通过，测试 VM `aos_test_*` 残留 0。
6. 方案/代码复审：代表 scope 每组仍两条 FULL，先者 included、后者 excluded；OpenAPI 仅展示先者 GET，非目标 PUT/POST/独立 GET 文档保留。没有调用任何业务 handler。
7. 8080 无监听，18181 仍为 PID 28077 旧进程且未重载；不称浏览器/线上验收 GREEN。
8. 精确提交 verification/代码并同步 D-waves、AOS CAS 与 Prime；旧 A0-V 真实十二 Run 的 row proof/Fleet/Owner/ACK/closure 仍无权威。
9. 下一波 W5c9y：分别锁住 Ontology detail PUT 与 Schedules run POST 的实际 matcher/文档，再做纯 decorator 元数据切片；全程不发写请求。

230 L0 挂起、dev-org 零 canary、商城源不读、unknown 不重发/不手工 `run_definition`、m1 单写不 push。
