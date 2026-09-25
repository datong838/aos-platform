# W5c9w｜六组参数形状路由的无执行 matcher 审计

## 上位/安全线

W5c9m/u：七组参数形状中 Dataset detail 后置已在 W5c9n 隐藏；尚有六组，含 AIP lineage GET、Ontology object-types detail GET/PUT、Schedules detail/runs GET 与 run POST。W5c9v 已处理三组 exact POST 文档，但不证明 shape 约束相同。必须逐组从真实框架 matcher 而非模板正则猜测分派。不得调用任何 GET/POST/PUT handler；18181 旧进程、8080 离线、原组 no-authority。

## 文件级和隔离读回

- 静态审 `runtime_write.py`/`phase3_aip_lineage.py`、`ontology.py`/`phase4_ontology_types.py`、`wave_ext.py`/`phase5_schedules.py` 的 route decorator、参数类型与依赖，及 FastAPI 当前 `_EffectiveRouteContext.matches`。只读取代码，不读商城源。
- 一次 90 秒、无 lifespan/端口/DB 的独立进程，显式后台开关 off。对六组代表 path+method 调用有效 route `.matches(scope)`，输出每组 FULL 候选端点顺序、`include_in_schema` 与 schema 是否双列，必要时区分动态段约束。不提供业务请求 body/授权，也不进入 handler。
- 若六组均先者 FULL、后者 FULL 且无 method/path 特例，下一波分只读 GET 与写 POST/PUT 两小切片，仅隐藏后置文档并用 endpoint-free 负例锁分派；若任一组不是双 FULL，停止对该组推断/修复，另立合同。
- 本波只 audit/verification，历史测试不冒充专项；D-waves/AOS CAS/Prime 收口。8080 浏览器离线。

## 九步

1. 复习 231/W5c9m/u/v；2. 计划先提交；3. 静态路径/约束审；4. 一次有界 matcher；5. 无代码专项；6. no-activation 复审；7. 浏览器离线；8. audit/verification/记忆；9. 自动下一波。

230 L0 挂起、dev-org 零 canary、商城源不读、unknown 不重发/不手工 `run_definition`、m1 单写不 push。
