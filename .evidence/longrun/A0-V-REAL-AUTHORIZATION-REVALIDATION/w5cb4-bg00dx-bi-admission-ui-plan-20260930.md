# W5CB4 BG00dx｜签名 BI 当前准入页面只读消费文件级方案

## 上位方案与现场

已复习 231/231-3/231-9、BG00dv/dw。安装、配置、启用各有独立权威；产品应显示缺口，浏览器不得自行授予权限。BG00dw 新增 `GET /v1/aip/production-contracts/responsibility-plans/bi-preparation/admission`，仅返回当前授权 actor 的 read-only 候选；`candidateReady` 仍非写授权，POST 会在单事务重验。当前正式实例 growth1.12、三身份/Host、六 active 实例仍未齐，真库只读。

## 页面合同

安装页现有职责候选链接增加当时的 installation revision/ETag，仅作刷新对比。上线审批页只在来源 installationId 为 UUID 时调用 SDK GET；严格解析响应 UUID、正整数版本、exact 模板引用、六实例版本和 blocker/candidateReady 一致性。只有响应 ID 与来源精确一致且当时 revision/ETag 相同，才显示“当前读回”；不一致时提示已漂移，要求回安装页刷新。读失败/403/404/未知一律显示无可执行结论，不枚举其他租户记录。固定 blocker code 显示中文下一动作；不将候选数、URL、测试账号或通用职责计划列表算成签名 BI 配置完成。

本波只读。即使候选快照无阻断，也只提示写入口待当前正式授权链和独立受控提交接线；不发 `bi-preparation` POST，不生成幂等键或 Receipt，不启 Host/worker/Provider。下一波如开放写入口，必须保留强 If-Match、同一幂等键、未知结果只读对账和服务端重新校验。

## 文件与 RED

1. `apps/web/src/api/aipProductionContracts/contracts.ts`、`parser.ts`、`index.ts` 及相邻 API 测试：严格响应模型、只读 GET；缺字段、版本错、`candidateReady` 与 blockers 不一致 fail-closed。
2. `apps/web/src/pages/s2/assetBundles/RuntimeInstallationPanel.tsx` 与测试：追加来源 revision/ETag；过期候选不显示可信链接。
3. `apps/web/src/pages/s2/ProductionContractsPage.tsx` 与测试：来源 ID 有效时读取；403/404、网络未知、源版本漂移、响应跨安装全部禁入；服务端 blocker 中文下一动作；无任何写命令。
4. 专项→累计前端测试和 TypeScript/Vite 构建→方案/代码复审。仅 browser-pilot 可用于浏览器截图；缺工具时如实登记未验收。

回滚只回退本波前端读链；当前/clone DB 不写，不读商城源，不碰 dev-org 正向，不重放旧 12 Run，不手工 run_definition，不 push。
