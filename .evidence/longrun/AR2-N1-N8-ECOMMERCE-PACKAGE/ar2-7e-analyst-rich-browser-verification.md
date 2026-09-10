# AR2-7E Analyst 非空隔离功能验收

日期：2026-09-10

分支：`m1`

权威：`AOS-000572 / AR2_7D_RUNTIME_WIRING_CANONICAL_ROUTER_GREEN`

结果：`AR2_7E_ANALYST_RICH_BROWSER_GREEN`

## 1. 实施范围

- 产品代码零修改；新增固定浏览器执行器、隔离 canonical fixture、机器可读结果、三视口截图、失败诊断截图和本验证文档。
- Analyst 七个只读经营视图保持同截止面、未知不伪零、假设不冒充结论；BusinessInvestigation 以当前租户 exact Case/Run/State/Artifact/Evidence/Review refs 驱动。
- 本轮只验证内部 Run 状态、DataRequirement、ReviewIssue 与 Handoff compile；不读取真实源、不启动 Agent/Provider、不物化 Task/Plan、不产生任何外部业务动作。

## 2. 浏览器验收

- `1280×720 / 1440×900 / 1920×1080`：`3/3 PASS`，无横向溢出。
- 每个视口均实点七个经营标签：经营总览、驱动因素、问题诊断、增长计划、效果复盘、证据链、数据质量；各视图按自身合同展示可信空、待补证、未知/非因果边界。
- 每个视口在生意探究内完成 `渠道视角 → 经营实体 → 分析记录 → Run` 三级选择，切换私域商城/微信小店与跨渠道同名 `store-shared` 后回到 `case-private-a`，旧实体投影未残留。
- 每个视口回读三阶段、`1/3` 进度、Checkpoint、四类 bound Artifact、Evidence exact/locator 区分和三条 canonical Timeline。
- 每个视口依次执行 `暂停 Run → 继续 Run → 提交 DataRequirement → 接受需求范围 → 接受阶段产物 → 编译 exact 交接`，合计 `writes=18`。
- 前五类状态写每视口的 `If-Match` 严格为 `"1" → "2" → "3" → "4" → "5"`，Idempotency-Key 唯一；每次 POST 后均以 canonical GET 收敛。
- Handoff compile 每视口返回 `TARGET_INSTANCE_NOT_READY`、`4/4 exact refs`、一次性凭证“页面未保留”；签发、接收和决定入口未出现。
- `otherWrites=0`、`forbiddenWrites=0`、`prohibitedWrites=0`、`unknownGets=0`、`tenantDrift=0`、`pageErrors=0`、`consoleErrors=0`。

## 3. 失败收敛记录

- 首轮在写入前停止：顶栏与业务面板同名“渠道视角”导致定位不唯一，且两个可信空视图使用了过度统一的字面断言；改为限定业务面板并按各视图结构断言。
- 第二轮完成前四次写后停止：旧 fixture 的 Review evidence/artifact 类型被当前 strict parser 拒绝；页面正确失败关闭。fixture 改为合同要求的 `Evidence` 与 `Artifact`，未降低产品校验。
- 第三轮完成六次写后停止：module handoff 的 ResponsibilityPlan hash 误带 `sha256:` 前缀；页面正确拒绝编译成功。只修正该 fixture 字段为 64 位 raw SHA-256。
- 第四轮三视口全绿；所有失败轮都遵守连续两次同阶段失败即停，且未发生 Handoff 签发或外部副作用。

## 4. 自动验证

- Analyst、BusinessInvestigation、investigation client/parser 定向：`4 files / 49 tests PASS`。
- Web 全量：`280 files / 2510 tests PASS`。
- production build：TypeScript 与 Vite 通过，`375 modules transformed`。
- `verify_closure.py --phase ar2-7`：`1711 scanned / 93 classified / 57 migrated`；六类错误数组全空。
- `git diff --check`：PASS。

## 5. 产品 hash 与方案一致性

- `AnalystPage.tsx`：`abfc9cc9ebb860afa951e1b20e9aa723b75797e71af5bceb3b21a238ce2e13e8`
- `BusinessInvestigationTab.tsx`：`fed6e97850fb6ac98bcacfa1f244dc2f2e23f32931048586d1edf8a0abcbc4`
- `AnalystPage.test.tsx`：`74ecb88255e8abd3356e570163c0da142f24ed8246e3fbd562e4f3853d94fc82`
- `BusinessInvestigationTab.test.tsx`：`92b72c741cdd67194237005cb00bf00766c719a43ade04d062d6645a68891b77`
- `ecommerceInvestigation/client.ts`：`e3fa63ad185a8f2d4c687e5a3068ce986884f7d4e3cd2eab826f95a83e179467`
- `45-ecommerce-workshop.css`：`c767b5a9351a7a21e24926b186a09f029c2dd662200b37af65ad2f3a9b9afb5e`
- 六个 hash 与方案冻结值一致；本轮没有修改既有功能和数据。

## 6. 边界与下一步

- `sourceReads=0`、`agentRunsStarted=0`、`providerInvocations=0`、`handoffsIssued=0`、`handoffsConsumed=0`、`handoffDecisions=0`、`tasksMaterialized=0`、`plansMaterialized=0`、`externalBusinessMutations=0`。
- 本绿态只证明隔离环境内的当前 UI、strict client 和 canonical 回读合同可工作，不证明栖月汇真实经营事实、真实计划批准、Handoff 可签发或外部执行完成。
- AR2-7E 八工作台富浏览器进度为 `8/8`；下一步按 closure manifest 汇总总体证据、复核动态引用并落阶段退出标记。230 L0 继续挂起，不 push。
