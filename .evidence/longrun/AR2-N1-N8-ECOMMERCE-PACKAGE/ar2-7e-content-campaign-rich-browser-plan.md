# AR2-7E 内容活动非空隔离功能验收方案

日期：2026-09-10

分支：`m1`

基线：`a253d6b1`

权威：`AOS-000572 / AR2_7D_RUNTIME_WIRING_CANONICAL_ROUTER_GREEN`

状态：执行器编码前冻结

## 1. Rules 与依据

- 承接 231-6 第 161 条与八页面动作表：逐页验证三视口、全菜单、折叠、滚动、非空数据、按钮、筛选、刷新和回读；本页必须实点创建／编辑／保存活动、日历、模板、生成／重新生成、风险建议、版本评审和结果查看。
- AR2 仍只使用隔离合同 fixture；商品、库存、活动与草稿均为无真实凭据、客户数据和经营结果的合成记录，不冒充 A0-V/A1 的栖月汇真实只读数据。
- 正式活动数据保持 GET-only。内部草稿命令与审批前预览只允许由 Playwright 路由截获，不能到达后端、数据库、Provider 或发布通道。
- “批准并发布”在本页只执行审批前预览，必须返回 `approvalAllowed=false` 与待补条件；不得形成 Approval、TaskRun、外部发布或业务 mutation。
- 同一视口连续失败两次即停止；不通过删除动作或降低合同断言取得绿色。

## 2. 施工文件和当前哈希

- 计划新增执行器：`.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/ar2-7e-content-campaign-rich-browser.mjs`
- 计划新增机器证据：同目录 `ar2-7e-content-campaign-rich-browser.json`
- 计划新增三张正式截图：同目录 `ar2-7e-content-campaign-rich-{width}x{height}.png`
- 计划新增验证说明：同目录 `ar2-7e-content-campaign-rich-browser-verification.md`
- `apps/web/src/components/workshop/ContentCampaignPage.tsx` preHash：`872a27c9cec6cd2a30b703a5fef8fdeb65c8d5f82bb3f46e28c755968251a5ed`
- `apps/web/src/api/ecommerceWorkshop/client.ts` preHash：`83a8d9a826def5a3712f3fc6f203250503eec52442ebcefab53c2a768471f2ff`
- `apps/web/src/api/ecommerceWorkshop/parser.ts` preHash：`1bbe80ee9a232d640ef482c4fb75e00ba706ef0a40916d6393677b6e8d323cc8`

默认不改产品源码；若验收发现产品缺陷，先补独立修复方案，再做最小修改。

## 3. 三视口固定动作

每个独立 context 在 `1280×720`、`1440×900`、`1920×1080` 执行：

1. 加载三切片非空 exact facts、两项隔离商品、一项低库存 SKU 和一项正式活动排期，核对数量守恒、CampaignRevision、MasterContentIntentRevision、ContentVariant 与 `variant_of` lineage。
2. 实点三主页签；在内容日历切换“内容排期／任务计划表”，选择第二件商品并核对价格、库存和关联 SKU；在日常模板切换“全部／运行中／已暂停”，保持可信空模板边界。
3. 展开活动筛选，在“全部／内部草稿／正式记录”间往返；点击“新建活动”清空旧草稿，选择“读取正式活动计划”回填目标。
4. 依次执行生成、保存、重新生成；每次校验 current draftRef、expectedVersion、单一 Idempotency-Key、零副作用 ledger、递增版本和业务 Receipt。
5. 对折扣毛利与库存供给各执行一种风险决策，校验经营约束、来源版本和新版本；再撤销最近决策，验证版本继续前进且旧决定不被覆盖改写。
6. 点击“批准并发布”，只允许一次审批前预览；核对 `approvalAllowed=false`、待补正式预算／素材评审条件、Provider/Approval/TaskRun/外部发布/业务 mutation 全为零。
7. 点击页内重新读取并确认正式 GET facts 未被草稿写命令污染；折叠／恢复侧栏，滚动到末尾并截图。

## 4. 请求与退出条件

- `3/3 PASS`，每视口三页签、两日历子视图、三模板筛选、三活动筛选、两商品选择均完成。
- 每视口 workflow command 顺序严格为 `generate → save → regenerate → apply_risk_decision → apply_risk_decision → undo_risk_decision`，版本严格递增，Idempotency-Key 唯一；审批预览恰好 `1`。
- 所有写请求仅为上述被截获的 content-campaign workflow/preview；`networkContinuedWrites=0`，Provider、Approval、TaskRun、发布和外部业务 mutation 均为 `0`。
- 刷新后三切片与真实输入 fixture hash/count 不变；未知 GET、tenant header 漂移、HTTP 5xx、page/console error、水平溢出均为 `0`。
- Web 全量、production build、`verify_closure.py --phase ar2-7` 与 `git diff --check` 全绿。
- 本切片通过后继续 Operations 页面，不前推 7E authority。
