# 运行工作台前端目录消费与失效

基线 70d01cae。新增 apps/web/src/api/runtimeWorkshop.ts、对应测试，以及 components/extensions/RuntimeWorkshopCatalog.tsx 与组件测试。复用现有 tenantAuthHeaders / getApiBase 与 RuntimeUiSession 解析，避免连接旧电商业务 parser。必要时仅将 assetControl/runtimeInstallations.ts 的 parseUiSession 导出，不改变旧解析行为。

客户端校验 schema、响应租户、条数、唯一 route/moduleId、当前安装/代次/revision、资源哈希与 URL contentHash 一致、精确路由归属、resourceOnly=true。只消费签名模块的展示元数据，完整 provenance 保留校验。失败无旧目录回退。

Provider 请求开始即清空 entries，租户或权限事件无条件失效；序号与 scope 共同阻断晚到响应；卸载 abort。60 秒仅为显示缓存上限，刷新先卸载；不是服务端执行许可。后续宿主仍须每个 bridge 调用核对当前绑定及服务端权限。本波先交付客户端/Provider及竞态验证，不提前挂可执行 iframe，也不声称实际工作台业务已经接通。

资源加载边界：现有 extension_dispatch 仅承接九项运行命令与历史只读投影，尚无通用、当前运行身份绑定的 UI read/command 转发服务。后续不能简单把旧 HTTP 路径传给 iframe；需要先补服务端 bridge 门禁及包内只读端口，再接业务宿主。Provider 暂不挂 App，避免将尚未配置的能力显示成可用。
