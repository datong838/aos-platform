# AR2-7E Creator Growth 非空隔离功能验收方案

日期：2026-09-10

分支：`m1`

基线：`9e381292`

权威：`AOS-000572 / AR2_7D_RUNTIME_WIRING_CANONICAL_ROUTER_GREEN`

状态：浏览器执行器修改前冻结；产品代码预期零修改

## 1. Rules 与方案依据

- 231-6 要求候选筛选、详情、邀约计划、阶段推进、产物和跟进回读；合法候选、合同与触达同意是硬边界，无真实发送批准不得称已触达。
- 产品方案固定达人库、招募、商务签约、履约效果、长期关系五阶段；邀约是采集→文案→质检→人工批准→发送→回执的可审计流水线，不是一键群发。
- 当前 `CreatorGrowthPage` 已有五阶段、四筛选、检索、正式商品、六类内部准备、create/save/submit_review/approve/reject/restore、版本历史、Receipt 与重新读取。内部 workflow parser 强制四类 side effect 计数为 0。
- 本切片不新增产品功能；使用隔离合同 fixture 验证已有闭环。若截图或运行发现产品缺陷，先增补本方案并提交，再做最小修复。

## 2. 非空隔离数据与动作

- 五个 stage 各提供一条合法 stable authority ref；所有 `piiRefs=[]`，不提供姓名、联系方式或可直接触达 payload。
- 正式商品输入提供一条隔离商品；Creator contribution/lifecycle 提供内部批次、合同/交付/关系计数，但 `externalEffectsAllowed=false`。
- 点击五标签、四筛选；检索命中与可信空；核对五阶段工作区和三栏布局；打开六类准备面板并检查对应字段。
- 在 candidate_import 上完整执行 `create r1 → save r2 → submit r3 → reject r4 → save r5 → submit r6 → approve r7 → restore r8`，每步回读 history 与 Receipt。
- “批准”只改变内部 TaskBrief 状态，不调用外部联系、合同签署、寄样、佣金、Provider 或业务 mutation。

## 3. 证据文件

- 新增执行器、JSON、三张截图与验证文档：同证据目录 `ar2-7e-creator-growth-rich-*`。
- 产品文件只读基线：
  - `apps/web/src/components/workshop/CreatorGrowthPage.tsx`：`c336dae28979516b88746ff0e8cd3f1212b31422d760f7e8b4b9595aba9e46c7`
  - `apps/web/src/components/workshop/CreatorGrowthPage.test.tsx`：`f4f67d8c474988e22ee7ed85417edcf2a860804edf04b4ad8e7b2d56d2385500`
  - `apps/web/src/styles/45-ecommerce-workshop.css`：`c767b5a9351a7a21e24926b186a09f029c2dd662200b37af65ad2f3a9b9afb5e`

## 4. 三视口和 transport 断言

- `1280×720 / 1440×900 / 1920×1080` 每个独立 context 从零开始，固定完成全部动作、侧栏往返、滚动到底、截图与几何检查。
- 每个 workflow POST 必须有唯一 Idempotency-Key；非 create 命令必须携带当前 exact draftRef 与 expectedVersion；restore 必须携带明确 restoreRevision。
- 只允许内部 `/views/creator-growth/workflow/commands` POST；联系人解析、发送、合同签署、寄样、付款、佣金、Provider、发布与外部 mutation 请求均为 0。
- 页面与请求体不得包含 mobile、OpenID、email、address、contactValue 或真实达人身份字段。

## 5. 退出条件

- 三视口 `3/3 PASS`；五阶段、四筛选、检索、六准备面板、八步内部生命周期、Receipt/history、刷新和几何全部通过。
- 内部 command response 每步 `providerInvocationCount=0`、`externalOutreachCount=0`、`contractSignatureCount=0`、`businessMutationCount=0`。
- Creator 定向现有测试、Web 全量、production build、`verify_closure.py --phase ar2-7` 和 `git diff --check` 全绿；产品代码 hash 不变。
- 本切片通过后富浏览器进度 `6/8`，继续 Media Studio，不前推 AR2-7E 总体标记。

## 6. 首轮诊断与执行器修正（2026-09-10）

- 首轮在 `1280×720` 与 `1440×900` 均于初始回读停止，内部 workflow 写入为 0；两视口根因相同，按同阶段两次失败规则先停止并复核。
- 定位歧义：页面同时存在 AppShell `main.main` 与业务区 `main.creator-growth-main`。初始业务回读改为精确选择 `.creator-growth-main`，不改变产品 DOM。
- 路由漂移：产品客户端实际读取 `/api/v1/ecommerce-workshop/views/content-campaign/real-inputs`，执行器误写为 `/inputs`。fixture 路由改为产品客户端的真实路径。
- 修正范围只限浏览器证据执行器；保留首轮 FAIL JSON 与 diagnostic 截图直至绿态证据生成，产品文件 hash 退出条件不变。
