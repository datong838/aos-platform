# AR2-7E Creator Growth 非空隔离功能验收

日期：2026-09-10

分支：`m1`

权威：`AOS-000572 / AR2_7D_RUNTIME_WIRING_CANONICAL_ROUTER_GREEN`

结果：`AR2_7E_CREATOR_GROWTH_RICH_BROWSER_GREEN`

## 1. 实施范围

- 产品代码零修改；本切片只新增固定浏览器执行器、隔离 fixture、机器可读结果、三视口截图和本验证文档。
- 固定正租户为 `org-org/dev-project`；五阶段各一条 stable authority ref，所有 `piiRefs=[]`。
- 只允许内部 `/views/creator-growth/workflow/commands` POST；真实触达、合同签署、寄样、付款、佣金、Provider、发布和其他业务 mutation 保持关闭。

## 2. 浏览器验收

- `1280×720 / 1440×900 / 1920×1080`：`3/3 PASS`，无横向溢出。
- 每个视口均完成：五阶段切换、四筛选、检索命中/可信空/清空、六类准备面板字段回读、刷新、侧栏往返和滚动到底。
- 每个视口均完成 `create → save → submit_review → reject → save → submit_review → approve → restore revision 1`；合计 24 次内部草稿写入。
- 24 次命令均有唯一 Idempotency-Key；非 create 命令携带 exact draftRef、contentHash 和 expectedVersion；restore 明确携带 `restoreRevision=1`。
- `otherWrites=0`、`forbiddenWrites=0`、`unknownGets=0`、`tenantDrift=0`、`pageErrors=0`、`consoleErrors=0`。
- 截图人工复核：正式商品、候选 ref、三栏工作区、五阶段和零副作用文案可读；全局应用栏沿用既有紧凑布局，三视口均未发生页面横向溢出。

## 3. 失败收敛记录

- 首轮发现两个证据执行器问题：双 `main` 定位歧义、真实商品输入路径为 `/real-inputs`；均在内部写入前停止。
- 二轮发现整页文案被错误限定到中栏，以及“第 8 版”非唯一定位；路由、浏览器错误和外部写入已为零。
- 三轮发现历史倒序下 `first()` 恢复第 7 版；改为定位“第 1 版 · 草稿”所在 article 后恢复。
- 每轮相同根因在两个视口出现即停止复核；diagnostic 截图保留，最终 JSON 由全绿运行重新生成作为 canonical 结果。

## 4. 自动验证

- Creator 定向：`1 file / 13 tests PASS`。
- Web 全量：`280 files / 2510 tests PASS`。
- production build：TypeScript 与 Vite 通过，`375 modules transformed`。
- `verify_closure.py --phase ar2-7`：`1711 scanned / 93 classified / 57 migrated`；六类错误数组全空。
- `git diff --check`：PASS。

## 5. 产品 hash 与方案一致性

- `CreatorGrowthPage.tsx`：`c336dae28979516b88746ff0e8cd3f1212b31422d760f7e8b4b9595aba9e46c7`
- `CreatorGrowthPage.test.tsx`：`f4f67d8c474988e22ee7ed85417edcf2a860804edf04b4ad8e7b2d56d2385500`
- `45-ecommerce-workshop.css`：`c767b5a9351a7a21e24926b186a09f029c2dd662200b37af65ad2f3a9b9afb5e`
- 三个 hash 与方案冻结值一致，证明本切片没有把验收修正混入产品实现。

## 6. 边界与下一步

- 本绿态只证明隔离 fixture 下的页面读取和内部草稿治理闭环；不证明已联系达人、已签署合同、已寄样、已结佣或已产生外部经营效果。
- AR2-7E 富浏览器进度更新为 `6/8`；下一项为 Media Studio。230 L0 继续挂起，不 push。
