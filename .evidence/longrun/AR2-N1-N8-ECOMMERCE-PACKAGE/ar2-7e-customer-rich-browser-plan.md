# AR2-7E Customer 非空隔离功能补齐与验收方案

日期：2026-09-10

分支：`m1`

基线：`ed1f4e20`

权威：`AOS-000572 / AR2_7D_RUNTIME_WIRING_CANONICAL_ROUTER_GREEN`

状态：产品代码修改前冻结

## 1. Rules 与方案依据

- 231-6 要求 Customer 覆盖客户/分群、旅程、同意、内容草稿、执行记录、撤销与恢复；R7-C01～C06 要求合法汇总、内部闭环、最小披露和栖月汇 CustomerLite 自验收，真实消息发送单独许可。
- `17-客户关系技术方案.md` 固定 CustomerLite/Consent/Segment/Journey/Dialogue/Batch 的 tenant-scoped append-only authority；页面不得持有 protected contact，prepare/freeze 不解析联系方式、不创建渠道 Action、不调用 Provider、不发送。
- `产品方案v2/09-客户关系工作台.md` 要求 purpose/consent/retention/频控约束、Dialogue/Journey Brief 与 Evidence/Eval 版本、撤回立即阻断新动作、发送 unknown 进入 reconcile。
- 当前页面已有四视图、六轴、贡献链、治理计数和失败态，但非空客户只读卡片没有可操作的分群→旅程→对话草稿、版本、预览、记录、撤销与恢复路径。
- 本切片复用通用 AIP Action Proposal 表达内部客户经营草稿，不新增 contact resolve、Permit redeem、Provider dispatch、send 或真实导入 URL；隔离浏览器 fixture 不冒充栖月汇真实 CustomerLite/A0-V/A1 证据。

## 2. 产品最小补齐

- 增加 `全部 / 可披露 / 待复核 / 已排除` 最小投影筛选和 stable Customer ref 选择；页面只显示 resource id、purpose、授权状态、质量、留存、k 匿名和 evidence 数量，不展示姓名、mobile、OpenID、地址或 contact value。
- 右栏增加“内部客户经营计划”：选择业务类型（分群/旅程/对话草稿）、标题、purpose、分群条件、旅程阶段、合规内容草稿；创建 `ecommerce.customer.prepare-outreach-draft`、R2、`contactResolutionAllowed=false`、`providerDispatchAllowed=false`、`sendAllowed=false`、`externalEffectAllowed=false` 的 Action Proposal。
- 修改必须创建 replacement proposal，不覆盖旧版本；提供影响预览、timeline 执行记录、审批前预览、撤回。审批前预览只说明 Consent/频控/Approval/Lease/Permit/渠道门，不能调用 decision/lease/execute。
- 撤回后“恢复为新草稿”只恢复编辑内容；再次保存创建新的独立 proposal，不复用撤回 proposal 的执行权或幂等键。
- “导入客户预检”和“发送预检”只返回本地失败关闭 notice：导入需 source mapping/purpose/PII contract，发送需 contact resolver/Permit/Provider/单独许可；网络写请求为 0。
- 刷新四类正式 Customer GET 后清空内部草稿状态，正式投影不被本地计划污染。

## 3. 文件与 preHash

- `apps/web/src/components/workshop/CustomerPage.tsx`：`bad3354dc02bc9466fea10c58efffaaf0b05f33484403ab1b2586b36adce67dd`
- `apps/web/src/components/workshop/CustomerPage.test.tsx`：`50df2e5de7ca11f708241be6758c2aaec3f7656235404a657ad2451609b06bd2`
- `apps/web/src/styles/45-ecommerce-workshop.css`：`f3a491e24f7ce8c57cf56f72d25a2fe36fd1ff8e7177daa99924a7a8ea77129b`
- `apps/web/src/api/aipActions/client.ts`：`7bc57111c69c649c0ea36d9015fcae8881b258a661573cd12af54b92ebf6c37c`（只消费，不修改）
- 计划新增执行器、JSON、三张截图和验证文档：同证据目录 `ar2-7e-customer-rich-*`。

## 4. 单元与三视口固定动作

- 单元测试覆盖四筛选、可信空、stable ref 选择、草稿 create/replacement、影响预览、timeline、审批预览、撤回、恢复为独立新 proposal、导入/发送零 transport 和敏感字段不呈现。
- 每个 `1280×720 / 1440×900 / 1920×1080` context：切换四标签和四筛选；选择允许披露与待复核投影；展开六轴与累计审计；完成 `新建 → 保存 v1 → 预览 → 修改 → replacement v2 → timeline → 审批预览 → 撤回 → 恢复编辑 → 保存独立 recovery proposal`；执行导入/发送预检；刷新四个正式 GET；侧栏往返、滚动到底和几何检查。
- AIP POST 每视口只允许三组 create/submit 与一次 withdraw；timeline 为 GET。全部由 Playwright 路由截获，检查唯一 Idempotency-Key、draft CAS 和 withdraw CAS。

## 5. 退出条件

- 三视口 `3/3 PASS`；四标签、四筛选、两类 Customer ref、六轴、草稿 v1/v2/recovery、预览、审批前检查、timeline、撤回、刷新及页面几何全部通过。
- 页面和请求体不出现 protected contact/姓名/手机号/OpenID/地址；proposal payload 只含 stable ref 和允许的最小策略字段。
- Approval、Lease、Permit redeem、contact resolve、Provider、发送、导入、客户状态修改和外部业务 mutation 全为 0。
- Customer 定向、Web 全量、production build、`verify_closure.py --phase ar2-7` 与 `git diff --check` 全绿。
- 本切片通过后，八工作台富浏览器进度为 `5/8`；继续 Creator Growth，不前推 AR2-7E 总体标记。
