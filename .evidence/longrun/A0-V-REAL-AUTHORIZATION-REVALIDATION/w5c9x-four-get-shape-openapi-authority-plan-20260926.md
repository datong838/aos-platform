# W5c9x｜四组 GET 参数形状的无执行 OpenAPI 权威切片

## 上位与进入事实

复习 231 长程顺序/每波九步、230 L0 不授权、W5c9m/u/w 的实际 route 与 matcher 证据。W5c9w 六组代表路径双 FULL，先注册者在前；本波只处理四组 GET：AIP lineage detail、Ontology object-types detail、Schedules detail、Schedules runs。Ontology detail PUT 与 Schedules run POST 两组写方法仍单独冻结。18181 旧进程、8080 离线、原 A0-V 十二 Run no-authority。

## 精确文件与验收

- `services/aos-api/aos_api/routers/phase3_aip_lineage.py`：仅后置 `GET /lineage/{record_id}` decorator 设 `include_in_schema=False`；保留列表 GET。
- `services/aos-api/aos_api/routers/phase4_ontology_types.py`：仅后置 `GET /object-types/{ot_id}` decorator 隐藏；保留同形 PUT、count/properties 等独立路径。
- `services/aos-api/aos_api/routers/phase5_schedules.py`：仅后置 `GET /{sc_id}` 与 `GET /{sc_id}/runs` decorator 隐藏；保留 PUT、POST run、pause 与其它路径。
- 新增 `services/aos-api/tests/test_w5c9x_shape_get_openapi_authority.py`：`--noconftest`、无 lifespan/DB/端口，RED/GREEN 锁每组前后有效 route 顺序、代表 scope 双 FULL、schema 仅前者、OpenAPI 仅可达前者模板；锁住上述独立 GET/PUT/POST 文档不丢。不得调用任何 handler，包括 GET。

专项为新测试；累计为 manifest 全套及 W5c9n/q/r/s/t/v 文档测试，无测试 PG fixture。仅 decorator 元数据最小改动，不调路由顺序、路径、鉴权或业务逻辑；若静态审发现非双 FULL、方法共享 decorator 或当前 HEAD 漂移，先停代码修改，补证据。浏览器 8080 离线，不称线上 GREEN。完成 verification 精确提交、D-waves/AOS CAS/Prime 后自动规划写方法形状切片。

## 累计封印补充（RED 后、修改封印前）

专项 5 passed 后的累计显示业务 route count 4511 与哈希 `3ce493dbdcb5cc3069d515983399b336187d1eda400f8e9a0a5c6bec773c0c0d` 不变；仅 OpenAPI 路径键由 2710 变 2708。AIP `{record_id}` 与 Schedules `{sc_id}/runs` 只承载目标 GET，隐藏后键消失；Ontology `{ot_id}`、Schedules `{sc_id}` 同键还承载 PUT，因此保留。`test_domain_router_manifest.py` 的静态 OpenAPI paths 封印应精确改为 2708；不改变路由数量/哈希封印，也不将变化解释为运行时路由删除。改前须再次读回这四键实际 methods。

## 九步与停止

1. 上位产品/技术方案复习；2. 文件级方案先提交；3. 无执行 RED；4. 最小 decorator 修改；5. 专项与累计；6. 方案/代码/写方法一致性复审；7. 浏览器离线记录；8. verification/上下文/记忆；9. 自动下一波。

230 L0 挂起、dev-org 零 canary、商城源不读、unknown 不重发/不手工 `run_definition`、m1 单写不 push。
