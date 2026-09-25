# W5c9l｜FastAPI 有效路由精确碰撞审计方案

## 上位与已知缺口

W5c9k `m1@646ad427`/AOS-000699：两个分类器漏掉 `_IncludedRouter`，精确冲突 UNKNOWN；`phase5_datasets.py` 已注明两个 GET 不可达。依赖库 OpenAPI 生成使用 `fastapi.routing.iter_route_contexts(routes)` 展开有效路由。本波只纠正审计，不改路由/Operation ID 或真进程。

## 文件级和有界执行

- 静态复核当前 venv `fastapi/routing.py` 的 `RouteContext` 属性、`iter_route_contexts` 与 `fastapi/openapi/utils.py` 使用点，设计可正确取 effective path/method/unique ID 的分类器。
- 一次 90 秒短命进程，显式 Host=0/Cron=false/snapshot=false/migration disabled，其余后台 off；只导入 `aos_api.main.app`，不进入 lifespan、不开端口、不生成业务副作用。通过 `iter_route_contexts(app.routes)` 枚举有效 API 路由，精确统计重复 method/path 与 Operation ID；仅输出总量、有限路径/ID/端点模块名，避免 schema/参数/凭据全文。若 API 属性不符或异常即停止 UNKNOWN，不盲猜重试。
- 同时核对已知 `GET /v1/datasets` 与 `GET /v1/datasets/{ds_id}` 的注册顺序/endpoint；只读，不能靠调序把历史未达路由意外启用。
- audit/verification、D-waves/AOS CAS/Prime；修复若值得做必须下波先方案、负例/兼容测试。

## 九步

1. 复习 231、W5c9j/k 与零执行门。
2. 本方案先提交。
3. 静态检查迭代器数据结构。
4. 一次离线有界有效路由审计。
5. 无代码修改时专项为精确聚合，累计不复用为本波测试。
6. 检查“文档 ID 冲突”与“运行时 path/method 遮蔽”差别。
7. 8080 业务浏览器离线。
8. audit/verification、精确提交、D-waves/AOS CAS/Prime。
9. 自动下一波立文件级最小修复/兼容验证计划或转独立安全债；原组 no-authority 不变。

230 L0 挂起、dev-org 零 canary、商城源不读、unknown 不重发/不手工 `run_definition`、m1 单写不 push。
