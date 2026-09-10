# AR2-7E Media Studio 非空隔离功能验收方案

日期：2026-09-10

分支：`m1`

基线：`e689f4b6`

权威：`AOS-000572 / AR2_7D_RUNTIME_WIRING_CANONICAL_ROUTER_GREEN`

状态：浏览器执行器修改前冻结；产品代码预期零修改

## 1. Rules 与方案依据

- 231-6 要求无计划创建、输入关联、生成模态、版本、质检/评审、文件下载播放与恢复；每个已承诺模态必须对应真实有效文件，付费 Provider 调用按独立批准。
- 产品方案要求准备素材与启动 Job 分离；本地预览不作正式 Artifact，生成完成不作审核/发布成功；批准与发布分轴，恢复只能从兼容 checkpoint 继续。
- 本阶段没有付费 Provider、真实生成或发布授权，因此只验收内部生产任务、权威引用、质量/评审候选、可下载 JSON 交付清单和发布 Proposal。页面不得伪造图片、音视频文件或播放成功。
- 当前 `MediaStudioPage` 已提供三内容类型、内部任务创建与修订、历史、交付候选选择、清单导出和内部发布 Proposal；解析器强制 Provider、外部生成、费用、发布和业务 mutation 五类计数为 0。若浏览器证据发现产品缺陷，先补充本方案并提交，再做最小修复。

## 2. 非空隔离数据与动作

- 三个 slice 各提供一个 stable authority ref，六 readiness axis 使用 exact ref；不包含账户 Secret、Provider payload 或真实媒体身份数据。
- 初始内部任务列表为空；从“新建生产准备”创建 planting_copy r1，再按 exact draftRef/CAS 顺序执行：`save_input r2 → attach_evidence r3 → reassign r4 → pause r5 → resume r6 → prepare_sample r7 → select_template r8 → schedule r9 → return r10 → prepare_live r11 → prepare_batch r12`。
- 每个命令回读当前状态、Receipt 和连续历史；每次非 create 请求必须携带上一版 revision、contentHash 与 expectedVersion。
- r12 交付 workspace 提供一个通过质量门、ReviewIssue 已解决、returnDecision 可回读的隔离 Artifact 候选；用户显式选择后才能导出清单和提交内部发布审批。
- 导出返回真实 `application/json` 内容并触发浏览器下载；发布 Proposal 只生成 pending 内部审批对象，`publicationCount=0`。

## 3. 三视口交互和 transport 断言

- `1280×720 / 1440×900 / 1920×1080` 各使用独立 context，从空列表创建任务并完成全部 12 版流程。
- 核对三个 Tab、三筛选、检索命中/可信空/清空、历史 12 版、交付候选、质量检查、复核与退回计数、下载事件、Proposal 回执、刷新、侧栏往返和滚动到底。
- 允许的 POST 仅为内部 workflow commands、JSON exports 和 publish-proposals；禁止 provider job/start、generation、upload、platform publish、fee/charge/settlement 和其他外部 mutation。
- 所有 Idempotency-Key 唯一；租户固定 `org-org/dev-project`；unknown GET、tenant drift、page error、console error、横向溢出均为 0。

## 4. 证据文件与产品 hash

- 新增执行器、JSON、三张绿态截图、必要 diagnostic 截图和验证文档：同目录 `ar2-7e-media-studio-rich-*`。
- 产品只读基线：
  - `apps/web/src/components/workshop/MediaStudioPage.tsx`：`ed1b92079ef49f675ad0f3c0437c9e027b66ebe4a5745f643bd91c10b060c766`
  - `apps/web/src/components/workshop/MediaStudioPage.test.tsx`：`1af3496776b104420e82cc0134cab1d0e9eac9c0d0d9390ccc0179b7bd454b70`
  - `apps/web/src/styles/45-ecommerce-workshop.css`：`c767b5a9351a7a21e24926b186a09f029c2dd662200b37af65ad2f3a9b9afb5e`

## 5. 退出条件

- 三视口 `3/3 PASS`；每视口 12 次 workflow、1 次 export、1 次 publish Proposal，外部副作用计数全部为 0。
- Media Studio 定向现有测试、Web 全量、production build、`verify_closure.py --phase ar2-7` 与 `git diff --check` 全绿；产品代码 hash 不变。
- 本切片通过后富浏览器进度 `7/8`，继续 Analyst，不前推 AR2-7E 总体标记。

## 6. 首轮诊断与 root-stage 修正（2026-09-10）

- `1280×720` 与 `1440×900` 均在任何写入前失败关闭；请求全部命中并返回 200，页面保持 failed boundary。
- 严格 parser 要求 `brief_profile` 阶段包含 exact `rootBriefRef`，`compile_start` 阶段包含 exact `taskRunRef`。首版 fixture 在两个阶段使用了另造 Artifact ref，触发 root-stage drift。
- 修正只把前两阶段 exactRefs 绑定到既有根引用；数量守恒、后续阻断和全部零副作用边界不变，产品代码不改。

## 7. 二轮诊断与折叠区/hash 修正（2026-09-10）

- root-stage 修正后两个视口均完成 12 次 workflow、1 次 export 和 1 次 publish Proposal 请求；其他写入、受禁写入、unknown GET、页面与控制台错误为 0。
- 完整视频场景与 authority ref 位于默认折叠的治理/数据审计区；执行器改为显式展开对应 details 后回读，不要求隐藏文本在初始可见区出现。
- Proposal fixture 的 `proposalHash` 使用了非十六进制字符，严格 parser 拒绝回执；改为合法 64 位小写十六进制 SHA-256。产品代码和副作用边界不变。
