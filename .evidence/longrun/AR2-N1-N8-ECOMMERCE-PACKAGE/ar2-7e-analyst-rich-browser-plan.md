# AR2-7E Analyst 非空隔离功能验收方案

日期：2026-09-10

分支：`m1`

基线：`7d6d4d45`

权威：`AOS-000572 / AR2_7D_RUNTIME_WIRING_CANONICAL_ROUTER_GREEN`

状态：产品代码修改前冻结

## 1. Rules 与方案依据

- 231-6 要求 Analyst 覆盖渠道、经营实体、Case 三级选择，三阶段、全标签、计划/定时、继续/暂停、审查与 Handoff；事实必须同一截止面，缺失不得伪零，假设不得当结论。
- `12-经营参谋生意探究工作区产品方案.md` 固定一个长期 Case 内串行推进“经营画像 → 问题与机会 → 方案设计”，并要求 Case/Run/revision/evidence/checkpoint 可追溯；数据不足只能形成 DataNeed，不能直接读源库或猜测补齐。
- 当前 `AnalystPage.tsx` 已提供经营总览、驱动因素、问题诊断、增长计划、效果复盘、证据链、数据质量七个只读标签；`BusinessInvestigationTab.tsx` 已提供三级选择、Run/StageRail、DataRequirement、ReviewIssue 和 Handoff 编译入口。
- 本切片先以隔离 canonical fixture 验证现有实现。只有可复现的产品缺陷才追加最小修复方案；不得为迎合脚本改写真实合同。
- 允许的隔离内部写仅为 Run pause/resume、DataRequirement request/confirm、ReviewIssue accept 和 Handoff compile。Handoff compile 必须返回 blocked 且 side effects 全零；不得签发、消费或接受 Handoff。
- 禁止真实源读取、模型/Agent/Provider 调用、Task/Plan 物化、客户触达、发布、调价、退款、发货、费用或外部业务写入；230 L0 单独授权事项继续挂起。

## 2. 验收动作

- 每个视口先验证经营参谋模块、八页导航、单一 H1、当前租户和同截止面正式只读投影，再逐项切换七个经营标签，检查未知值仍显示“未知”。
- 进入默认“生意探究”，依次切换两个渠道、同名跨渠道经营实体、每个实体各自 Case 与 Run，证明上游选择变化会清空旧投影，且请求始终携带 `org-org/dev-project`。
- 核对同一 Case 的三阶段轨道、当前步骤、Checkpoint、贡献区、四类正式产物、证据下钻、时间线、数据门和审查区域。
- 在隔离响应中逐次执行 `暂停 Run → 继续 Run → 提交 DataRequirement → 接受需求范围 → 接受阶段产物`；每次校验唯一 Idempotency-Key、If-Match 版本递增、POST 后 canonical GET 精确收敛。
- 填写已批准 GrowthPlan exact ref，执行一次 Handoff compile；服务端返回 `TARGET_INSTANCE_NOT_READY`，页面必须展示阻断、4/4 exact refs、零 side effects，且不出现签发、接收或决定入口。
- 刷新页面后重新读取 Case/Run/View/Review，验证服务端最终投影；侧栏折叠/展开、主滚动区到底后归顶，并检查三个桌面视口无横向溢出。

## 3. 文件与 preHash

- `apps/web/src/components/workshop/AnalystPage.tsx`：`abfc9cc9ebb860afa951e1b20e9aa723b75797e71af5bceb3b21a238ce2e13e8`
- `apps/web/src/components/workshop/BusinessInvestigationTab.tsx`：`fed6e97850fb6ac98bcacfa1f244dc2f2c2e23f32931048586d1edf8a0abcbc4`
- `apps/web/src/components/workshop/AnalystPage.test.tsx`：`74ecb88255e8abd3356e570163c0da142f24ed8246e3fbd562e4f3853d94fc82`
- `apps/web/src/components/workshop/BusinessInvestigationTab.test.tsx`：`92b72c741cdd67194237005cb00bf00766c719a43ade04d062d6645a68891b77`
- `apps/web/src/api/ecommerceInvestigation/client.ts`：`e3fa63ad185a8f2d4c687e5a3068ce986884f7d4e3cd2eab826f95a83e179467`
- `apps/web/src/styles/45-ecommerce-workshop.css`：`c767b5a9351a7a21e24926b186a09f029c2dd662200b37af65ad2f3a9b9afb5e`
- 计划新增固定执行器、JSON、三张截图和验证文档：同证据目录 `ar2-7e-analyst-rich-*`。

## 4. 退出条件

- `1280×720 / 1440×900 / 1920×1080` 三视口 `3/3 PASS`；七标签、三级选择、三阶段、四产物、证据/时间线、五步内部状态流和 blocked Handoff 全部实点通过。
- 允许写总数每视口固定为六次：pause、resume、request missing data、confirm requirement、review accept、handoff compile；其他写、未声明 GET、跨租户、敏感字段、浏览器错误均为 0。
- Handoff issued/consumed/decision、AgentRun、Provider、真实源读取、Task/Plan 物化及全部外部业务副作用为 0。
- Analyst/BusinessInvestigation 定向测试、Web 全量测试、production build、`verify_closure.py --phase ar2-7` 与 `git diff --check` 全绿。
- 本切片通过后，八工作台富浏览器进度为 `8/8`；随后按 closure manifest 补齐 AR2-7E 总体证据和阶段退出标记，不前推 230 L0。
