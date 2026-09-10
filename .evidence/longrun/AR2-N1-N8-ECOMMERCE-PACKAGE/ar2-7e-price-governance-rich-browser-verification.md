# AR2-7E Price Governance 非空隔离功能验证

日期：2026-09-10

分支：`m1`

权威：`AOS-000572 / AR2_7D_RUNTIME_WIRING_CANONICAL_ROUTER_GREEN`

方案提交：`b41fef68`；截图缺陷增补：`022a9159`

结论：`PASS`

## 1. 实现与方案一致性

- 保留三类正式只读视图与六轴 readiness；新增全部、可比、待复核、已排除四类观察筛选和 exact 观察选择。
- 内部价格策略只调用现有 AIP Action Proposal：创建 v1、replacement v2、对比预览、timeline 回读与撤回；载荷固定 `externalEffectAllowed=false`、`repricingAllowed=false`。
- 批准预览与立即采集预检只改变本地 UI notice，没有 decision、lease、execute、ResearchJob、Provider、通知或调价 transport。
- 刷新重新读取 price governance、research contribution、typed disposition 和 three-module closure 四类正式 GET；内部草稿不写回价格领域读模型。
- 首轮截图发现 300px 观察栏继承三列布局，导致文本逐字竖排；已按方案增补改为 primary visual 单列，并在 1365px 以下让卡片 header 纵向排布。三视口几何断言均通过。

## 2. 固定浏览器验收

执行器：`ar2-7e-price-governance-rich-browser.mjs`

结果文件：`ar2-7e-price-governance-rich-browser.json`

- `1280×720`：PASS
- `1440×900`：PASS
- `1920×1080`：PASS
- 每视口：三标签、四筛选、两观察选择、六轴审计、策略 v1/v2、对比、timeline、审批预览、采集预检、撤回、四类 GET 刷新、侧栏往返和滚动到底均完成。
- 三视口共 15 个内部 Action Proposal POST，均在 Playwright route 截获；每视口严格为 create draft、submit v1、create replacement draft、submit v2、withdraw v2。
- 正式 GET 读取 36 次；`otherWrites=0`、`forbiddenWrites=0`、`unknownGets=0`、`pageErrors=0`、`consoleErrors=0`。
- 每张价格观察卡宽度至少 181px；市场标题在各视口均不超过四行。页面 `nav=8`、`h1=1`，无 document 横向溢出。

截图：

- `ar2-7e-price-governance-rich-1280x720.png`
- `ar2-7e-price-governance-rich-1440x900.png`
- `ar2-7e-price-governance-rich-1920x1080.png`

## 3. 自动验证

- Price Governance 定向测试：`1` 文件、`9/9 PASS`。
- Web 全量：`280/280` 文件、`2509/2509 PASS`。
- Production build：TypeScript 通过，Vite `375 modules transformed`，构建成功；仅有既存的 500 kB chunk 提示。
- `verify_closure.py --phase ar2-7`：扫描 Python module `1711`，classified `93`，migrated `57`；`hashErrors`、正反向未分类依赖、跨层 import 和 dynamic reference errors 全为空。
- `git diff --check`：PASS。
- Prime GitHub Copilot 只读产品差异复核：PASS；该复核没有覆盖当时尚未跟踪的 Playwright 文件，浏览器证据以实际运行结果为准。

## 4. 零副作用与风险

- `approvalCount=0`、`leaseCount=0`、`executionCount=0`、`repricingCount=0`、`researchJobCount=0`、`notificationCount=0`、`providerInvocationCount=0`、`externalPublicationCount=0`、`externalBusinessMutationCount=0`。
- fixture 仅代表隔离合同记录，不代表栖月汇真实数据或 A0-V/A1 验收。
- 调价仍需独立授权、审批、短时租约与 R4 专业门；本切片不扩大 authority。
- 230 L0 保持挂起；没有 production migration、release 或 push。

## 5. 文件哈希

- `PriceGovernancePage.tsx`：`49f622ca5660deb70560a3d195642de5b3a7b4567cd4cc33e198283f71d02916`
- `PriceGovernancePage.test.tsx`：`848d44abc7b9bcf5f9516fb8399070c3a5db5c89cde47e4b5f463bee1b42a049`
- `45-ecommerce-workshop.css`：`f3a491e24f7ce8c57cf56f72d25a2fe36fd1ff8e7177daa99924a7a8ea77129b`
- 浏览器执行器：`9668dfbe0bc024df30a746e05c64cc969b8e08feaa6b81b44ae6c0de39a84e91`
- JSON 证据：`fecd7dfbf9f5369db9994a1ca83b7a73fda171068a3f24d57a0334d880241a03`
- 1280 截图：`bffb7bc18909e31eb3e222fad746310792387e8d80b5bfe28fb8c36c6a6b3c78`
- 1440 截图：`157c81ad409be3e81765ee4c8b7e1b2b3545cc630b834007b75dacbee2946458`
- 1920 截图：`5d80bbca2837140ba8c4c630fda94404549947caf84b1ffc2d27e784a9e21af4`

## 6. 阶段路由

Price Governance 非空隔离功能补齐完成；AR2-7E 八工作台富浏览器进度为 `4/8`。下一项串行进入 Customer，仍不前推 AR2-7E 总体标记。
