# W5c9j｜离线 OpenAPI 冷/热生成计量方案

## 上位边界

承接 W5c9i `m1@3343a5ee`/AOS-000697：真实 18181 首次 5s 超时、第二次 200/5.24MB；准确冷耗时未知。原组 no-authority、商城源禁读、8080 业务浏览器离线、真实 API 租约不改。

## 文件级与执行范围

- 只读复核 `services/aos-api/aos_api/main.py`、`ontology_contract_openapi.py` 和纯 HTTP flags；本波先不改代码。
- 新建**独立短命进程**，禁 Cron/Host/snapshot/migration/自动化，导入 `aos_api.main.app` 但不进入 FastAPI lifespan、不调用服务路由、不绑定端口。最多一次 `app.openapi()` 冷生成和一次热返回；计量 wall time、路由数量与序列化 schema 字节数，只打印聚合，不打印 schema/凭据。进程 90 秒有界，超限即停/记录未知，不重试；不访问 PG 或商城源。
- 若 import/openapi 隐式尝试外部连接或超时，冻结并单独诊断，不推测。若可复现高冷成本，仅归类技术性能债；任何预热/并发修复都必须另立方案、RED/GREEN、真实功能安全复审。
- 审计/verification、D-waves/AOS 上下文更新；8080 离线，不宣称业务浏览器验收。

## 九步

1. 复习 231、W5c9i 与零执行现场。
2. 本方案先提交；复查 exact `m1`/18181/租约。
3. 静态确认 app import 与 schema 构建调用链。
4. 一次有界隔离计量；必要时补方案后才改代码。
5. 无代码时专项为计量与静态核对，累计历史结果不冒充。
6. 方案/代码/风险一致性复审。
7. 8080 业务浏览器离线。
8. audit/verification、精确提交、D-waves/AOS CAS/Prime。
9. 自动下一波按计量结果决定性能小修或独立安全债；原组 ACK/closure 冻结。

230 L0 挂起、dev-org 零 canary、unknown 不重发/不手工 `run_definition`、m1 单写不 push、不读商城源。
