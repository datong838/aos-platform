# 运行目录客户端验证

基线 70d01cae。独立目录 parser/client 与 RuntimeWorkshopCatalogProvider；只复用通用 RuntimeUiSession 解析，不依赖旧业务页面。刷新、租户/权限事件立即清空，过期重读，AbortController+请求序号+主体 scope 阻止晚到结果。资源 URL contentHash、模块路由、摘要与运行身份均校验。

红测在补齐 Node PATH 后确认缺失 Provider；实现后 3 个测试文件 15 项通过，整站 tsc --noEmit 通过，diff --check 通过。覆盖重复目录、租户错配、资源摘要、路由、执行代次、resourceOnly、刷新失败、晚到响应、60 秒失效以及既有 runtime parser 回归。

本波未挂 App、未创建 iframe；尚未交付签名前端资源、服务端 UI bridge 读写转发和包内业务页面。消费目录不等于业务执行许可。下一波先落服务端 bridge 当前身份/声明门禁与固定命令转发方案，再逐项补包内读取端口，最后接 UI；不直接使用旧业务 HTTP 绕过领域包。
