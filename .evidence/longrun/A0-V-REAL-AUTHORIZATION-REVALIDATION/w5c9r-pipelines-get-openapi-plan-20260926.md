# W5c9r｜Pipelines 重复 GET 文档权威最小切片

## 上位/边界

承接 231、W5c9l/m 的有效路由碰撞、W5c9n/q 的无分派变化范式及 W5c9p 的无 DB 路由测试。`GET /v1/pipelines` 先 `wave_ext.list_pipelines`、后 `phase5_pipelines.list_pipelines`；同路径的 POST 也重复，**本波绝不处理或重排 POST**。18181 旧代码未重载、8080 业务浏览器离线、原组 no-authority。

## 文件级清单

- 先静态核实 `services/aos-api/aos_api/routers/phase5_pipelines.py` 的后置 GET 与其它 POST/详情；仅对该 GET decorator 加 `include_in_schema=False`，不动 endpoint、路径、鉴权/注册顺序/其它方法。若 GET 包含多方法或另有参数形状冲突，停止补方案。
- 新增 `services/aos-api/tests/test_w5c9r_pipelines_get_openapi_authority.py`：RED 锁后置 GET 原先仍公开；GREEN 锁两 route 仍注册、前置 `wave_ext` 文档权威、后置 GET 不进 schema、POST 和合法详情文档仍保留。绝不调用 GET/POST handler。
- 全部测试 `--noconftest` 且后台 flags off；专项与 manifest + W5c9n/q 文档累计。浏览器 8080 离线，不重启 18181。
- verification/代码精确提交，D-waves/AOS CAS/Prime；下一波继续 GET-only，写端点需要单独兼容门。

## 九步

1. 复习上位；2. 本计划先提交；3. RED；4. 一行最小改动；5. 专项/累计；6. 方案/代码/POST 未变复审；7. 浏览器离线如实记录；8. 证据/记忆/提交；9. 自动下一波。

230 L0 挂起、dev-org 零 canary、商城源不读、unknown 不重发/不手工 `run_definition`、m1 单写不 push。
