# W5c9s｜Schedules 重复列表 GET 文档权威最小切片

## 上位边界

承接 231、W5c9l/m 的有效路由基线、W5c9n/q/r 的最小文档去重与 W5c9p 的无 DB 测试。`GET /v1/schedules` 先 `wave_ext.list_schedules`，后 `phase5_schedules.list_schedules`；同路径 POST 和七组参数形状碰撞中的 Schedules detail/runs/run 都不在本波范围。18181 旧代码、8080 离线、原组 no-authority。

## 文件级与验证

- 先静态核 `services/aos-api/aos_api/routers/phase5_schedules.py` 的单独 GET decorator；仅加 `include_in_schema=False`，不改 endpoint、注册顺序、鉴权或 POST/run/pause。
- 新增 `services/aos-api/tests/test_w5c9s_schedules_get_openapi_authority.py`：RED 锁当前后置 GET 仍进 schema；GREEN 锁两 GET route 仍注册、前置 `wave_ext` 文档权威、后置 GET 不进 schema、POST/run 文档仍保留。不调用处理器。
- `--noconftest`、所有后台 flags off，专项 + manifest/Dataset/Builds/Pipelines 累计；不启动 DB/Worker/源/18181 重载。8080 浏览器离线。
- verification/精确提交/D-waves/AOS CAS/Prime；下一波另选 GET-only 或参数形状文档切片，写路由另门。

## 九步

1. 上位复习；2. 方案先提交；3. RED；4. 最小 decorator；5. 专项/累计；6. 方案/代码/POST 不变复审；7. 浏览器离线；8. 证据/记忆/提交；9. 自动下一波。

230 L0 挂起、dev-org 零 canary、商城源不读、unknown 不重发/不手工 `run_definition`、m1 单写不 push。
