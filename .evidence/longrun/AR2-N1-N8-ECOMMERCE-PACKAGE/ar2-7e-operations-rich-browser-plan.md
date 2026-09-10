# AR2-7E 统一运营非空隔离功能验收方案

日期：2026-09-10

分支：`m1`

基线：`331bf8c4`

权威：`AOS-000572 / AR2_7D_RUNTIME_WIRING_CANONICAL_ROUTER_GREEN`

状态：执行器编码前冻结

## 1. Rules 与依据

- 承接 231-6 第 161 条与八页面动作表：逐页验证三视口、全菜单、折叠、滚动、非空数据、按钮、筛选、刷新和回读；本页必须实点来源计数、筛选、订单／售后详情、内部处理草稿、审批前预览与请求级 Receipt。
- AR2 只使用隔离合同 fixture；订单、售后、库存、运营工单和处理候选均为不含真实客户信息、凭据和经营结果的合成记录，不冒充 A0-V/A1 的栖月汇真实只读数据。
- 七类正式运营视图、命令就绪度、处理候选与请求级观察保持 GET-only。内部 Action Proposal 草稿、替代版本和撤回仅允许由 Playwright 路由截获，不能到达后端或数据库。
- “批准预览”只展示独立审批人与执行租约前置条件，不调用批准、租约、执行、退款、发货或其他外部动作。
- 同一视口连续失败两次即停止；不通过删除动作、缩减断言或改用真实业务数据取得绿色。

## 2. 施工文件和当前哈希

- 计划新增执行器：`.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/ar2-7e-operations-rich-browser.mjs`
- 计划新增机器证据：同目录 `ar2-7e-operations-rich-browser.json`
- 计划新增三张正式截图：同目录 `ar2-7e-operations-rich-{width}x{height}.png`
- 计划新增验证说明：同目录 `ar2-7e-operations-rich-browser-verification.md`
- `apps/web/src/components/workshop/OperationsPage.tsx` preHash：`9bbfe04c78a0774a3fd3c0a536e5b62691c12e65763b9e98da835cef36daa757`
- `apps/web/src/api/ecommerceWorkshop/client.ts` preHash：`83a8d9a826def5a3712f3fc6f203250503eec52442ebcefab53c2a768471f2ff`
- `apps/web/src/api/ecommerceWorkshop/parser.ts` preHash：`1bbe80ee9a232d640ef482c4fb75e00ba706ef0a40916d6393677b6e8d323cc8`

默认不改产品源码；若验收发现产品缺陷，先补独立修复方案，再做最小修改。

## 3. 三视口固定动作

每个独立 context 在 `1280×720`、`1440×900`、`1920×1080` 执行：

1. 加载七类非空正式视图、两项内部处理候选和六项 blocked 命令就绪度；核对来源总量、已挂接、未匹配、冲突、页计数、同租户和同一数据截止。
2. 实点“全部／订单与履约／库存与告警／售后与工单”四类筛选；搜索命中订单、搜索无结果并清空，验证候选与正式视图均按输入收敛且可信空提示出现。
3. 在订单与售后事件间切换正式业务视图；分别打开原始业务对象和处理日志，核对 ReadAuthority、版本、Receipt、数据截止与数量解释后关闭。
4. 展开处理建议依据、页面完整 SOP 与内部处理 SOP；验证建议只来自当前数量守恒和正式来源，并明确外部动作另行审批。
5. 对隔离候选执行 `新建处理 → 采纳建议 → 保存并提交审批 → 处理日志 → 修改 → 提交修改 → 批准预览 → 驳回/撤回`；严格核对草稿创建／提交、timeline、替代草稿创建／提交、撤回顺序，精确 CAS 与唯一 Idempotency-Key。
6. 输入隔离提案和租约引用读取请求级观察，核对状态、ActionReceipt、OperationAuthorityReceipt、提案哈希与“禁止自动重放”。
7. 点击页内重新读取并确认七类正式 GET facts 未被内部草稿命令污染；折叠／恢复侧栏，滚动到末尾并截图。

## 4. 请求与退出条件

- `3/3 PASS`，每视口四类筛选、订单与售后详情、两个日志面板、建议依据、两类 SOP、内部处理完整版本链、批准预览、Receipt 回读均完成。
- 每视口 Action 写序列严格为 `create draft → submit draft → create replacement draft → submit replacement draft → withdraw replacement proposal`，timeline GET 恰好一次；提交与撤回携带精确版本／哈希，所有写请求各有唯一 Idempotency-Key。
- 所有写请求仅为上述被截获的内部 Action Proposal 操作；`networkContinuedWrites=0`，批准、租约、执行、退款、发货、Provider、外部发布和真实业务 mutation 均为 `0`。
- 刷新后七切片、候选、命令就绪度 fixture hash/count 不变；未知 GET、tenant header 漂移、HTTP 5xx、page/console error、水平溢出均为 `0`。
- Web 全量、production build、`verify_closure.py --phase ar2-7` 与 `git diff --check` 全绿。
- 本切片通过后继续价格策略页面，不前推 7E authority。
