# W5CB4 BG00dv｜签名 BI 配置入口只读引导文件级方案

## 上位方案与现场

已复习 231、231-3、231-9、BG00dr–du。安装、配置、运行分别成立；六数字同事复用 AgentInstance，UI 不重算权限或 ready。现有 `RuntimeInstallationPanel` 展示八类租户候选及 `/aip/production-contracts` 链接；该候选只说明数量，不绑定安装。现有 `ProductionContractsPage` 主要呈现媒体生产职责计划，不能把该列表或旧模板当签名 BI 准备完成。服务端 `POST /responsibility-plans/bi-preparation` 已有当前 OIDC、权限、安装 ETag、签名来源、六 active 实例和同事务 Receipt 门，但当前真库缺正式正向条件，新操作 Receipt 为零。

## 本波行为

在运行实例候选处解释签名 BI 职责计划仍需当前安装、正式 OIDC、六个 active AgentInstance、当前权限与精确模板核验；只读跳转携带 installationId 供返回原页，不把查询参数当权威。在职责计划页给出同一准备路径的只读禁入说明和原安装返回入口，避免用户把通用职责计划列表或候选数量当成 BI 配置已就绪。没有服务端当前准入投影时不开放写按钮、不在浏览器推断授权，不触发 `bi-preparation` POST。Host/worker/Provider 保持关闭。

## 文件与验证

1. `apps/web/src/pages/s2/assetBundles/RuntimeInstallationPanel.test.tsx` 加 RED：候选缺失时仍可读到签名 BI 精确条件；过期候选不显示数量/可执行结论；只读链接携带安装 ID。
2. `apps/web/src/pages/s2/assetBundles/RuntimeInstallationPanel.tsx` 只改职责候选文案、上下文链接与条件说明。
3. `apps/web/src/pages/s2/ProductionContractsPage.tsx` 加只读禁入说明和来源安装返回入口；在现有页面测试补断言，不扩展 API SDK 和路由。
4. 专项、相邻测试、类型/构建，代码与方案复审；浏览器仅用 browser-pilot。若工具不可用，明确未做交互截图，不以 HTTP 200 替代。

回滚只回退上述前端文案和测试；当前/clone 数据库只读，不写 dev-org，不读商城源，不重放旧 Run，不手工 `run_definition`，不 push。
