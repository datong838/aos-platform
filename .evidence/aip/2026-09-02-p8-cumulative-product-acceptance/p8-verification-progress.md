# AIP-P8 累计产品验收进度证据

> cutoff：2026-09-02T06:52:00+08:00
> branch：`m1`
> baseline：`6b843d87`
> Task：`AIP-P8-CUMULATIVE-PRODUCT-ACCEPTANCE`

## 已闭合子包

### P8A · 25 页菜单与控件矩阵

- Codex 内置浏览器逐页打开真实侧栏 25/25 个 AIP 菜单页面。
- 每页保存顶部、主内容底部、侧栏底部三类截图，共 75 张，分辨率 1280×720。
- 25/25 页面均可折叠并恢复侧栏，侧栏均保留 25 条 AIP 菜单链接与唯一 `aria-current`。
- 25/25 页面主区和侧栏均滚动到底；没有文档级横向溢出。
- 页面未出现 `未就绪`、`待完成`、`不可派发`、`尚未实现`、`页面占位`、`TODO`、`coming soon`。
- 逻辑编排三页签、分析师专注模式等无副作用交互已实际点击验证。

证据：`p8-page-matrix-initial.json`、`p8-safe-interactions-initial.json`、`screenshots/`。

### P8B · 合同与权威追溯

- `INTERACTION_HONESTY_MANIFEST` 从 17 页补齐到真实侧栏 25/25 页。
- 更正能力目录实际 owner：`CanonicalCapabilityPage/live`，不再引用旧 `CapabilityPage/mixed`。
- 新测试由 `NAV_ITEMS` 反向推导 25 页，逐页断言 live source、源码、fallback policy 和测试引用。
- `p8-contract-trace.md` 逐页记录前端 owner、router、authority、Receipt/Lineage 边界；明确禁止用 `traceId` 代替 `lineageId`。

### P8C · 双租户只读实测

- API `/v1/health` 返回 200/ok。
- `org-org/dev-project`：六位数字同事、10 项公共能力、6 个分析模板；模型运行权威返回 3 Provider、3 Route、3 Model。
- `dev-org/dev-project`：响应 tenant 精确回显 canary；模型运行权威为 0 Provider、0 Route、0 Model，未泄漏正向租户运行数据。
- 全过程只有 GET，业务写入、Provider 调用、外部副作用均为 0。

证据：`p8-dual-tenant-read-probe.json`。

### P8D · 累计质量门

- Web 全量：270 files / 2410 tests GREEN。第一次默认高并发执行出现 11 个 UI 时序/超时失败；将 worker 限制为 4 后同一 2410 项全部通过，失败集合单跑 20/20 通过，判定为测试资源竞争而非产品回归。
- API AIP 核心累计现场重跑：114 passed，覆盖 Assist、Analyst、六数字同事/能力、文档智能、模型运行权威。
- TypeScript `tsc --noEmit`：GREEN。
- Vite production build：GREEN（367 modules）。
- `git diff --check`：GREEN。

### P8E · 多视口、缩放、键盘与可访问性

- Codex 内置浏览器完成 1280×720、1440×900、1920×1080 三档 25/25 页面稳定态复验。
- 200% 页面缩放在分析师页实测通过，主区与侧栏可见、无文档级横溢、无超大固定浮层。
- 25 页累计审计 3317 个可交互控件；无名称控件 0、错误 roving tabindex 0、主区/侧栏缺失 0、横向溢出 0。
- 两类导入预检、谱系/可观测可信空态、模型目录/运行就绪和文档模板版本交互均补充实测。

证据：`p8-viewport-accessibility.json`、`p8-safe-interactions-final.json`、`p8-real-browser-scenarios.json`。

### P8F · 交付闭环

- 安全提交：`d957745b`（25 页清单/合同/初始浏览器证据）与 `8a6c551c`（多视口、语义、真实场景与最终交互证据）。
- Delivery Receipt：`AIP-P8-CUMULATIVE-PRODUCT-ACCEPTANCE.json`。
- authority CAS：`AOS-000447 → AOS-000448`。
- memory status：强一致投影（01、06、project、WorkBuddy、Prime 三项）全部 `CURRENT`；Codex note 为 eventual `PENDING_ASYNC`。
- memory validate：`GREEN`；memory gate：`can_change_state=true`、`GREEN_WITH_WARNINGS`。
- Prime exact readback：`aos-current-delivery` version 458，`project_revision=AOS-000448`，P8 completed 与 `132_OF_132` delivery status 一致。

## 最终结论

P8A～P8F 以及总控 AIP-P0～P8 共 132/132 项在本次范围内闭合。该结论是代码、浏览器、合同追溯与双租户产品验收 GREEN，不授权 Provider、密钥解析、真实客户触达、业务发布/改价/发送、迁移、路由切换或 Release。

## 一致性与安全复审

1. 本波产品代码仅修改诚实交互清单及其覆盖测试；未改变业务数据、租户、安全、迁移、Provider、发布或外部副作用逻辑。
2. P6D 验证文档、`ModelRuntimePage.test.tsx`、`plugins/ops` 和历史未跟踪证据保持原状且不进入本提交。
3. P8E 已由本 episode 的内置浏览器证据闭合；P8F 仍必须按 Receipt → 安全提交 → authority CAS → memory/Prime 回读顺序完成，不能用本文件提前外推完成态。
