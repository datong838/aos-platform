# 路由前端会话接入当前运行投影与 HTTP

基线 26bbe4b8，承接 runtime-workshop-routed-ui-plan.md 第 2 项的只读会话部分。修改 services/aos-api/aos_api/extension_runtime/runtime_view.py、routers/bundle_runtime_installations.py；在 tests/extension_runtime/ 新增路由投影/HTTP 用例。

现有 GET /v1/bundle-runtime-installations/{installation_id} 可选单一 route 查询参数（1..512 字符，精确 canonical 路由，重复值拒绝）；不改变旧请求行为。租户、roles、markings 仍取 Principal，只将所选路由传入当前 ready RuntimeView 的签名前端 resolver；disabled/fenced/旧安装 revision 不解析 UI。

该 GET 不写数据，不颁发持久授权、不接受客户端 generation/epoch/权限 claims。保留 current-ready 边界及旧调用兼容；HTTP无效路由只返回固定安全提示。工作台运行目录、桥接能力和签名包构建继续后续切片。本片结束前准备部署新 API 并实际只读验收：现有包无 frontend 时仍应 ui=null，不能假装页面已交付。
