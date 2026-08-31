# AIP P6A 模型目录与供应商运行关系验证

- 任务：`AIP-P6A-MODEL-CATALOG-PROVIDER-CONTINUATION`
- 清单范围：P6-094～P6-101
- 租户：`org-org/dev-project`
- 权威基线：`AOS-000438`
- 方案依据：`164-AIP全菜单业务可用性缺陷总控与分批整改清单.md`
- 外部副作用：0；未刷新 Provider Health、未调用模型、未保存配置、未发布、未切换生产流量。

## 方案与实现一致性

1. 模型目录只读取当前租户的模型管理与运行权威；读取失败不回落静态演示目录。
2. 每个目录模型以 exact `RegisteredModelRevision` 关联 Provider、Route、EvalGate、Health、Capacity 与计价权威。
3. Provider 详情只展示凭据 backend/version，不读取、传输或回显 opaque ref 与 Secret payload。
4. 3/3 探针只认可受控 R2 writer 的同一 exact Provider、同一截止面元数据；过期证据明确显示“3/3 证据已过期”。
5. 模态、使用许可、禁止能力和计价状态使用中文业务表达；未知扩展枚举保留原值，避免篡改权威事实。

## 真实数据只读核验

- 模型目录：3 个，均来自当前租户权威服务。
- 模型：Agnes 2.5 Flash（文本）、Agnes Image 2.1 Flash、Agnes Video v2.0。
- exact Provider：3；exact Route：3；文本模型上下文为权威 33K，不采用旧静态 128K。
- 文本模型计价：已审批免费；图像/视频：计价单位待补，不冒充免费。
- Agnes 文本 Provider：1 个关联模型、1 个容量池、1 条路由解析；Health 截止面已过期，运行继续失败关闭。

## 自动化验证

- `parser.test.ts`、`ModelCatalogPage.test.ts`、`ProviderDetailPage.test.tsx`：53/53 GREEN。
- Web TypeScript：`tsc --noEmit` GREEN。
- `git diff --check` GREEN。

## 内置浏览器验收

- `p6a-model-catalog.png`：真实模型目录、中文模态/许可、平台授权与模型启用视图可工作。
- `p6a-provider-detail.png`：exact Provider、凭据安全摘要、3/3 探针截止面、模型/容量/路由关系与跨页入口可工作。
- 两页完整侧栏均包含八个已安装工作台和全部 AIP/模型管理入口，可折叠、可滚动。

## 结论

P6A 的目录、供应商、凭据安全显示、FeatureActivation 入口和 exact 运行关系已达到代码、专项测试、真实租户只读核验与浏览器证据闭合条件；真实模型调用和 Health 刷新不在本任务内，且未被执行。
