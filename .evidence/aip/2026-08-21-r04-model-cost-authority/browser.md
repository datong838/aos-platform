# R04 模型运行与成本权威浏览器验收

- 时间：2026-08-21（Asia/Shanghai）
- 浏览器：Codex 内置浏览器
- 前端：`http://localhost:5174`
- 组织/工作区：`org-org / dev-project`（栖月汇商贸有限公司 / 默认工作区）
- 验收方式：逐页导航、等待真实 API 完成、读取可访问性 DOM；未执行 Provider 调用、真实写入或 Secret payload 读取。

| 页面 | URL | 真实结果 | 交互结论 |
|---|---|---|---|
| 模型供应商 | `/aip/model-providers` | Canonical Provider=3，route ready=0/3；兼容 Provider 标记“非运行权威”；插件只标记“插件配置就绪” | 默认网关选择/保存禁用，不把插件配置冒充运行就绪 |
| 模型路由 | `/aip/model-router` | Canonical route ready=0/3，页面展示 blocker | 路由选择、保存、试聊、下钻和熔断演练禁用；审计导出保留 |
| 模型目录 | `/aip/model-catalog` | 三个 exact 模型可读；缺失或不兼容价格显示“计价单位待补” | 未知价格不显示为免费 |
| 容量管理 | `/aip/capacity` | Usage Receipt 权威可读；当前“无可归集成本” | 0 调用不覆盖历史 Receipt；未观测不等于 0 |
| 运行就绪 | `/aip/model-runtime` | Exact Provider/Model/Route/Policy/Eval/Health/Price/Capacity 快照可读；Health 过期与 route blocker 可见 | blocked 状态诚实，不刷新 Health、不外呼 Provider |

额外检查：

1. 五页均显示“组织 · 栖月汇商贸有限公司”和“默认工作区”。
2. DOM 未发现 `AGNES_API_KEY`、`sk-*` 或 Secret payload。
3. `/aip/model-runtime` 的正确路由已复核；错误路由 `/aip/runtime-readiness` 会回到首页，不作为验收证据。
4. 浏览器控制通道出现一次 Statsig 外网遥测超时，但本地五页导航和 DOM 读取全部完成，不影响 AOS 验收结论。
