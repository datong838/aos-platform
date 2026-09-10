# AR2-7E Media Studio 非空隔离功能验收

日期：2026-09-10

分支：`m1`

权威：`AOS-000572 / AR2_7D_RUNTIME_WIRING_CANONICAL_ROUTER_GREEN`

结果：`AR2_7E_MEDIA_STUDIO_RICH_BROWSER_GREEN`

## 1. 实施范围

- 产品代码零修改；新增固定浏览器执行器、隔离 fixture、机器可读结果、三视口截图、diagnostic 截图和本验证文档。
- 三个媒体 slice 和六类 readiness axis 使用当前租户 stable exact refs；完整视频场景保留 7 阶段、8 责任、9 故障轴与外部门阻断。
- 本阶段没有 Provider 或真实生成授权；不伪造图片、音视频文件或播放成功。可交付文件仅为本机浏览器实际接收的内部 JSON 清单。

## 2. 浏览器验收

- `1280×720 / 1440×900 / 1920×1080`：`3/3 PASS`，无横向溢出。
- 每个视口从空列表创建任务，完成 12 个连续 revision：`create → save_input → attach_evidence → reassign → pause → resume → prepare_sample → select_template → schedule → return → prepare_live → prepare_batch`。
- 每个视口均回读三 Tab、三筛选、检索命中/可信空/清空、12 版历史、质量通过候选、已解决 ReviewIssue 与一次 ReturnDecision。
- 用户显式选择交付候选后，每个视口实际触发一次 `media-media-brief-isolated-r12.json` 下载和一次 pending 发布 Proposal；页面明确回读“当前仍未执行外部发布”。
- 合计 `workflowWrites=36`、`exportWrites=3`、`proposalWrites=3`；`otherWrites=0`、`forbiddenWrites=0`、`unknownGets=0`、`tenantDrift=0`、`pageErrors=0`、`consoleErrors=0`。
- 每个非 create 命令、export 和 Proposal 均携带当前 exact draftRef 与 expectedVersion；workflow 和 Proposal Idempotency-Key 齐备。
- 截图人工复核后将外层内容区和三栏内部滚动位置归零，最终图可同时审查页面身份、摘要、Tab、任务、历史和交付区。

## 3. 失败收敛记录

- 首轮在写入前失败：完整视频 fixture 的 `brief_profile/compile_start` 未复用 exact rootBrief/taskRun，严格 parser 正确失败关闭。
- 二轮已完成全部内部动作，但隐藏审计文本被当作初始可见文本，且 Proposal hash 包含非十六进制字符；改为显式展开审计区并使用合法 SHA-256。
- 绿态后只调整截图取证位置，没有放宽功能、传输或副作用断言。

## 4. 自动验证

- Media Studio 定向：`1 file / 14 tests PASS`。
- Web 全量：`280 files / 2510 tests PASS`。
- production build：TypeScript 与 Vite 通过，`375 modules transformed`。
- `verify_closure.py --phase ar2-7`：`1711 scanned / 93 classified / 57 migrated`；六类错误数组全空。
- `git diff --check`：PASS。

## 5. 产品 hash 与方案一致性

- `MediaStudioPage.tsx`：`ed1b92079ef49f675ad0f3c0437c9e027b66ebe4a5745f643bd91c10b060c766`
- `MediaStudioPage.test.tsx`：`1af3496776b104420e82cc0134cab1d0e9eac9c0d0d9390ccc0179b7bd454b70`
- `45-ecommerce-workshop.css`：`c767b5a9351a7a21e24926b186a09f029c2dd662200b37af65ad2f3a9b9afb5e`
- 三个 hash 与方案冻结值一致；证据修正未进入产品实现。

## 6. 边界与下一步

- `providerInvocationCount=0`、`externalGenerationCount=0`、`feeChargeCount=0`、`publicationCount=0`、`businessMutationCount=0`。
- 本绿态不证明生成了媒体文件、调用了付费模型、完成平台发布或产生经营效果；这些仍需独立授权和真实 Receipt。
- AR2-7E 富浏览器进度更新为 `7/8`；下一项为 Analyst。230 L0 继续挂起，不 push。
