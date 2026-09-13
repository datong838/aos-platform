# UQ5-A2 App路由与导航

基线c9f32927，m1单写、不push、230 L0挂起。App挂运行目录Provider；canonical路径仅在runtime ready及legacy ready/empty且无同路径声明时加载RuntimeWorkshopHost。冲突或未知不加载；现有legacy路径保持原Host。侧栏追加真实runtime条目，不构造legacy权限DTO；签名页面沿通用头部，不启用旧专属按钮。

旧目录scope tenantKey合同保持，新增subject/roles/authRevision捕获与变化清空、迟到拒绝；同身份reload保持原stale行为。主区域空态可选reload回调刷新两目录，旧组件默认不传不变。

44 tests passed（runtime路由/导航6、旧目录/导航/八页面Host/AppShell与通用导航38），TypeScript全量检查通过，git diff --check通过。基线EcommerceWorkshopHost已有“当前工作台入口不可用”，三个AppShell断言仍旧写“模块未安装”，按原现行产品文案修正；未通过倒退产品误判来迎合测试。

## 真实浏览器

2026-09-13约21:09–21:13，复用同一IAB标签（重置CUA会话后浏览器id由3重映射为1，标签1未关闭）。先读原/apollo/assets，Registry四包可见；导航http://127.0.0.1:5173/workshop/analyst，org-org/dev-project，页面完成目录加载后显示“当前工作台入口不可用”及核对配置/权限说明，无伪造iframe或业务按钮。主区域“重新读取目录”按钮实点后显示“正在读取已安装工作台目录…”，随后回到真实空态。AX及截图均已在本轮工具输出核验。

当前增长包仍未交付signed UI，因此空态符合实际，不能视为真实读取通过。主库仍030、API/原宿主未升级，旧九命令不切换。下一波UQ5-B后继增长包独立只读operation及签名UI/范围声明；operations-base另包保持7+1；之后UQ6规范升级安装与真实读取，UQ7经营首链八场景。runtime旧别名尚不硬编码映射，需后继声明验证。
