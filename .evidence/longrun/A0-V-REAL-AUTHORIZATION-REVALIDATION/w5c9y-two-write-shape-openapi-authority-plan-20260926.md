# W5c9y｜两组写方法参数形状的无执行 OpenAPI 权威切片

## 上位与边界

复习 231 九步/A0-V 真实准入、230 L0 挂起、W5c9w 双 FULL matcher 与 W5c9x GET 文档切片。剩余 Ontology detail PUT `/v1/ontology/object-types/{type_id}` 对 `{ot_id}`、Schedules run POST `/v1/schedules/{schedule_id}/run` 对 `{sc_id}/run` 的代表 scope 都是先者与后者 FULL；前者先注册。前者 run handler 可真实触发 live pipeline，**任何情况下都不得调用 POST/PUT handler 或 HTTP 写请求**。本波只修改文档可见性，不修改业务执行权威。

## 文件级最小清单

- `services/aos-api/aos_api/routers/phase4_ontology_types.py`：只给后置 `PUT /object-types/{ot_id}` decorator 设 `include_in_schema=False`；不改同路径的 GET（已隐藏）、count/properties 等。
- `services/aos-api/aos_api/routers/phase5_schedules.py`：只给后置 `POST /{sc_id}/run` decorator 隐藏；不改同前缀的 GET/PUT、pause、runs。
- 新增 `services/aos-api/tests/test_w5c9y_shape_write_openapi_authority.py`：不进入 lifespan/DB/端口、不调用 handler，固定代表 scope 两条 FULL、先者在前、schema 前者 true 后者 false、OpenAPI 只展示前者写方法，独立 PUT/POST 文档保留。用 `--noconftest` RED/GREEN。
- 若 OpenAPI 路径数改变，先读回保留 methods、补方案，再精确调整 `services/aos-api/tests/test_domain_router_manifest.py` 封印；不得仅凭累计失败改数字。

专项新测试；累计 manifest 与 W5c9n/q/r/s/t/v/x 文档测试。方案/代码一致性包含真实 route count/hash、不变的前者鉴权与模板、以及无真实执行。18181 旧进程不重载，8080 浏览器离线。verification/精确提交/D-waves/AOS CAS/Prime 后再决定下一小波，不扩大到原十二 Run 的 ACK/closure。

## 九步

1. 上位复习；2. 方案先提交；3. endpoint-free RED；4. 两 decorator 最小修改；5. 专项/累计；6. 代码/方案/no-effect 复审；7. 浏览器离线；8. 证据和上下文；9. 自动下一波。

230 L0 挂起、dev-org 零 canary、商城源不读、unknown 不重发/不手工 `run_definition`、m1 单写不 push。
