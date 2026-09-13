# 运行时工作台只读目录 HTTP 接入

基线 03abc3dd。新增 GET /v1/runtime-workshop/modules，与旧电商目录分离。仅 require_principal 提供租户、角色、marking，客户端参数不能指定权限或切换租户。响应 no-store；安全的固定错误，不泄漏库表或连接信息。

修改文件：services/aos-api/aos_api/asset_registry/control_wiring.py 添加惰性只读目录构造器，ControlPlane 使用同一 RuntimeViewReader；services/aos-api/aos_api/main.py 配置无 lifespan 只读回退；services/aos-api/aos_api/routers/domain_aggregates.py 注册独立 routers/runtime_workshop.py。测试位于 tests/extension_runtime/test_runtime_workshop_http.py。

构造不访问数据库、不启动运行任务。首个读取才实例化受控 allowlist/trust roots 的 ManifestLoader 与共用候选 source。读取错误整体失败，绝不回退旧目录或授权执行。测试真实 HTTP 序列化、认证、租户/权限取自主体、no-store、故障与服务缺失、无副作用构造。真实安装暂无 frontend，线上空目录为预期，不作为工作台完成证据。

接线复核：domain_aggregates.py 是生成文件，正式来源为 routers/domain_manifest.json；独立运行资源目录应归 infra（与安装运行控制相邻），在 manifest 注册后由 scripts/generate_domain_aggregates.py 重新生成，并同步 tests/test_domain_router_manifest.py 的 infra 数量断言。保持既有路由顺序及重复项不变。
