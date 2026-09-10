# AR2-7E Customer 非空隔离功能验证

日期：2026-09-10

分支：`m1`

权威：`AOS-000572 / AR2_7D_RUNTIME_WIRING_CANONICAL_ROUTER_GREEN`

方案提交：`03e72102`

结论：`PASS`

## 1. 实现与方案一致性

- 四类正式只读视图和六轴 readiness 保持不变；新增全部、可披露、待复核、已排除四类最小投影筛选与 stable Customer ref 选择。
- 页面只展示 resource id、purpose、freshness/quality、Consent/retention、k-anonymity 与 evidence 数量；未增加姓名、mobile、OpenID、地址或 contact value。
- 内部客户经营计划通过现有 AIP Action Proposal 形成 v1、replacement v2、影响预览、timeline、审批前预览与撤回；撤回后的恢复保存为独立 proposal 和新幂等键。
- proposal 固定 `contactResolutionAllowed=false`、`providerDispatchAllowed=false`、`sendAllowed=false`、`externalEffectAllowed=false`。
- 导入客户预检与发送预检只更新本地 notice；刷新四类正式 Customer GET 后内部草稿清空，不污染正式投影。

## 2. 固定浏览器验收

执行器：`ar2-7e-customer-rich-browser.mjs`

结果：`1280×720 / 1440×900 / 1920×1080 = 3/3 PASS`

- 每视口完成四标签、四筛选、允许披露/待复核投影选择、六轴审计、v1/v2/recovery 三个 proposal、影响预览、timeline、审批预览、导入/发送预检、撤回、刷新、侧栏往返与滚动到底。
- 三视口共 21 个内部 AIP POST；严格为三组 create/submit 与一次 withdraw，全部在 Playwright route 截获。
- 正式 GET 36 次；`otherWrites=0`、`forbiddenWrites=0`、`unknownGets=0`、`pageErrors=0`、`consoleErrors=0`。
- 请求序列中的 draft CAS 与 withdraw proposal version/hash 全部匹配；7 个 Idempotency-Key/视口均存在且唯一。
- 请求序列不含 mobile、OpenID、address、contactValue；页面 `nav=8`、`h1=1`，无 document 横向溢出。

首轮执行器因 Customer contact route 名称写错返回 418，并被正确判为失败；修正为正式 client 路径后重跑。第二轮因固定标签栏遮挡自动点击以及 recovery 文案 locator 非唯一失败，均未改变产品业务逻辑；调整为确定性 DOM 点击与唯一 notice locator 后从三个视口完整重跑，旧失败结果被最终 JSON 覆盖。

## 3. 自动验证

- Customer 定向：`1` 文件、`11/11 PASS`。
- Web 全量：`280/280` 文件、`2510/2510 PASS`。
- Production build：TypeScript 通过，Vite `375 modules transformed`，构建成功；仅有既存的 500 kB chunk 提示。
- `verify_closure.py --phase ar2-7`：Python module `1711`、classified `93`、migrated `57`；hash、正反向未分类依赖、跨层 import 与 dynamic reference errors 全为空。
- `git diff --check`：PASS。

## 4. 零副作用与风险

- `approvalCount=0`、`leaseCount=0`、`permitRedemptionCount=0`、`contactResolutionCount=0`、`providerDispatchCount=0`、`sendCount=0`、`importCount=0`、`customerMutationCount=0`、`externalBusinessMutationCount=0`。
- fixture 只代表隔离 privacy-safe 合同，不代表栖月汇真实 CustomerLite、A0-V 或 A1 验收。
- 真实发送仍需最新 Consent/Preference、retention、频控 reservation、Approval、Lease、一次性 Permit、contact resolver、Provider 与独立许可；本切片不扩大 authority。
- 230 L0 保持挂起；没有 production migration、release 或 push。

## 5. 文件哈希

- `CustomerPage.tsx`：`7f3fca164e10a8e4f3aeb8fd512428879b670923562cf7af4d8b371798e6c1ee`
- `CustomerPage.test.tsx`：`32e1681458884d4d1f1a163d4eec4e7db9d9e1629c138e459b57f6492ba681e7`
- `45-ecommerce-workshop.css`：`c767b5a9351a7a21e24926b186a09f029c2dd662200b37af65ad2f3a9b9afb5e`
- 浏览器执行器：`29c5dca60d1456feee3c5ff6a655d377fff9e9e9adff0868cd020cb2a40c7fdf`
- JSON 证据：`a830644ba9ce8296e95b92898489a7d4d9769f10db0a220ee7e8342a7bde06dc`
- 1280 截图：`d36ad9208fa84ff79d5ab3ddbbdb829e5ae138b115d123a606c55c6b32e44414`
- 1440 截图：`aec886c7547c45187668ae13e8eeefc57d0af209de587aee51e0fbede44edd61`
- 1920 截图：`9a70eb4c5f1748ee60f77ade0a03908547785c00688206c0913494a271d1954e`

## 6. 阶段路由

Customer 非空隔离功能补齐完成；AR2-7E 八工作台富浏览器进度为 `5/8`。下一项串行进入 Creator Growth，不前推 AR2-7E 总体标记。
