# UQ5-A1 签名宿主读取桥接与身份失效

基线3d3975db，m1、不push、230 L0挂起。RuntimeWorkshopHost复用原ExtensionHost/Bridge安全协议，仅接固定analyst读取。pending沿原会话GET，未知提交不再次POST，并发读取拒绝，终态后新的read才新建会话。安装revision/binding revision参与整页key，变化卸载并abort；命令和产物下载不提供处理器。

tenant.ts提供无敏感信息的aos-auth-updated事件及单调authRevision；目录清空重读，读取会话拒绝ABA凭据变化。key仅含数字revision与资源元信息，不含Token。账号/scope变化及卸载取消旧宿主；无权资源不加载。

37 tests passed（宿主5、目录4、读取19、原ExtensionHost3、tenant6），全量TypeScript检查通过，git diff --check通过。原ExtensionHost测试仍有既有act环境warning，不影响断言。测试宿主以受控port和ExtensionHost探针隔离桥接行为；原iframe安全测试另行回归，未证明实际签名包页面或OCI调用。

尚未挂App路由与主侧栏，实际主库/API未改变。UQ5-A2直接衔接App Provider/路由选择/侧栏；同时旧目录同租户subject/凭据变化也需清空，双目录同canonical路径拒绝，不选未知来源。后继包签名和真实升级仍待UQ5-B/UQ6。
