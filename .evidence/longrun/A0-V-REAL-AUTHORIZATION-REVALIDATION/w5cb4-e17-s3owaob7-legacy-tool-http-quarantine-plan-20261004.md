# E17-s3o-w-ao-b7｜旧内存 Tool HTTP 入口禁入方案

## 上位方案与现场

复习 W2-B 220 §2.2 的进程内 `ToolRegistry`/Logic `use_tool`、231/BIND-1 的当前签名/安装/租户/Receipt 合同、b5/b6 正式 ToolDefinition 缺口。旧 `routers/tool_registry.py` 提供 `/v1/tools/register` 接受 Python 代码并 `exec`、`/invoke`、删除与 Capability 内存写；`domain_aggregates.py` 仍装载整个 router。当前原 API `/openapi.json` 逐项显示 register/invoke/delete `security=[]`，未认证 `GET /v1/tools` 为200空表。此旧入口不能作为正式 ToolBinding 来源。

## 文件级最小切片

1. 在 `services/aos-api/tests/` 加公开路由 RED，要求现行 API 不暴露旧 `/v1/tools*`、`/v1/capabilities*` HTTP 路由；旧内存 `ToolRegistry` 的 Python 内部注册/Logic 用法保持。测试只读检查真实 app router，不发 POST/DELETE、无业务副作用。
2. 原 `domain_aggregates.py` 是由 `domain_manifest.json` 生成且要求后续约500项 order 连续；直接改生成物或删除 manifest 条目会造成大范围重排。只在 `services/aos-api/aos_api/routers/tool_registry.py` 移除旧 HTTP 路由装饰器，保留普通函数、内存注册表和 Logic Python 接缝，AIP aggregate 装载空 router。未来正式签名 ToolDefinition 另走受限发行 API。此切片不修改 ToolBinding 原 DTO/Receipt、DB/migration或权限表。
3. 跑目标 RED→GREEN、旧 `test_tool_registry.py`、路由相邻回归；读回当前 API 若适用须按最新代码受控重启质量门后才能宣称 live 生效。浏览器页面若无相关可见入口可只读核 API 路由与现有工作台禁入；证据不得把旧 HTTP 关闭当正式 Tool 正向。

原库只读，Host/worker/Provider关，不读商城源、不重放旧12 Run、不手工 Run、不碰230 L0、不 push。
