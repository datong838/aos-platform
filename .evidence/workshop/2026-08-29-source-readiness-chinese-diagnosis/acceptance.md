# 八菜单共享 SourceReadiness 中文诊断验收

## 边界

- 任务：`WORKSHOP-SOURCE-READINESS-CHINESE-DIAGNOSIS-20260829`。
- 只修改共享 SourceReadiness 前端投影、专项测试和对应样式；未修改后端 readiness 判定。
- 未手工运行、重放或补跑 P01～P12，未调用 Provider，未读取或输出凭据/端点/PII，未制造业务数据，未执行真实业务写入、迁移或发布。

## 实现事实

- 十二类 canonical 数据对象在首层使用中文业务名称；英文对象类型、pipeline id、blocker code 与稳定 error code 仅保留在折叠审计详情。
- 八种 readiness 状态均有中文投影；未知审计码使用“需要进一步核对数据条件”兜底，不显示为成功或 0。
- SSH/MySQL 连接类失败给出“检查数据连接后等待下一次计划读取”；通用执行失败给出“查看运行审计后等待下一次计划读取”；过期数据给出“等待下一次计划读取更新数据”。
- 汇总按非 ready 数据对象计数，不再把“blocker 数组为空”误写为零待处理对象。

## 测试

- 专项：`SourceReadinessPanel.test.tsx`，4/4 GREEN；覆盖 blocked/failed/stale/unknown、稳定错误码、未知 fallback、未知 count、403、tenant mismatch、显式重读、审计详情折叠/展开/恢复。
- 相关链路：SourceReadiness/API parser/client/shared context/host/shell，67/67 GREEN。
- Web 全量：256 files、2325/2325 GREEN。
- TypeScript 与 production build：GREEN。
- `git diff --check`：GREEN。

## 内置浏览器与真实数据回读

- 在同一浏览器中逐项点击八个正式菜单：日常任务总控、内容与活动、统一运营、达人邀约、多媒体、经营参谋、价格治理、客户关系；八页均挂载同一份 SourceReadiness 快照且无页面级横向溢出（总控页浏览器度量差 6px，为既有舍入，不产生可见横向滚动条）。
- 当前快照检查时间与 cutoff 均为 `2026-08-29T13:15:56.225644Z`：12 个对象、8 个 ready、4 个待处理对象。
- P03 商品规格：failed，62 / 62，`数据读取运行失败 → 查看运行审计后等待下一次计划读取`。
- P07 发货履约：failed，19 / 19，`数据读取运行失败 → 查看运行审计后等待下一次计划读取`。
- P10 系统配置：failed，39 / 39，`数据读取运行失败 → 查看运行审计后等待下一次计划读取`。
- P12 支付：stale，210 / 210，`数据已超过新鲜度期限 → 等待下一次计划读取更新数据`。
- 八页默认视觉模式按既有 1:1 蓝图隐藏“模块安装上下文”，因此没有把技术表格新增到业务首屏；浏览器从八页 DOM 逐项回读共享组件，折叠交互由真实组件专项测试闭合。该边界保持页面视觉比例不变。

## 一致性复审

- 方案要求的“中文业务对象/状态/原因/下一步 + 审计码可追溯”已实现。
- 真实失败、过期和未知均未改判 ready，源/投影数量未改写，历史运行事实未修改。
- 发现并修复浏览器实测缺陷：旧实现按唯一 blocker code 数量显示“待处理条件 0”，与 3 failed + 1 stale 冲突；现改为“待处理对象 4”。

## 裁决

`SOURCE_READINESS_CHINESE_DIAGNOSIS_CODE_TEST_BROWSER_GREEN_NO_EXTERNAL_EFFECT`
