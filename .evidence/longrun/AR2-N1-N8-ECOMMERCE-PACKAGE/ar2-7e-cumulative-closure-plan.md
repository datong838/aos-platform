# AR2-7E 累计闭合实施方案

日期：2026-09-10

施工分支：`aos-platform/m1`

基线：`9a72e287`

当前 authority：`AOS-000572`

目标退出标记：`AR2_HOST_WIRING_CUTOVER_PLUGGABILITY_BROWSER_ACCEPTANCE_GREEN`

## 1. 权威与边界

本次仅按 `closure-manifest.md`、`dynamic-reference-phases.json`、`verify_closure.py`、231-6 实施方案和 `AR2-7D-RUNTIME-WIRING-CANONICAL-ROUTER` Delivery Receipt 闭合 AR2-7E。AR2 使用无真实凭据和客户数据的合同 fixture、隔离 capability 与真实代码制品；不调用真实 Provider，不执行真实租户业务 mutation、生产/共享迁移、外部发布或 push。`230 L0` 继续挂起。

Prime 仅作本地独立只读审查与开发记忆辅助；GitHub Copilot OAuth 凭据只保存在本机 `~/.prime/agent/auth.json`，不进入 AOS 产品、运行依赖、仓库或证据正文。

## 2. 累计输入

1. AR2-7D 已以 `AOS-000572` 和 Delivery Receipt 闭合 Canonical Router、host composition、cutover、lifecycle、旧 Router 转发及自然槽位路由。
2. 7E shell capability gating、页头动作 authority、浏览器 console 分类均已有专项方案与验证。
3. 八工作台入口/失败关闭矩阵为 37/37 PASS；有效隔离数据矩阵为 24/24 PASS、24 张截图齐备。
4. 任务总控、内容计划、统一运营、达人邀约、多媒体、经营参谋、价格治理、客户运营八个富交互专项均已完成三视口验证、刷新回读、租户隔离和副作用边界检查。
5. 所有累计输入必须是当前 Git 可追溯文件；未提交诊断图、临时日志和历史未跟踪文件不得进入最终闭合。

## 3. 实施步骤

1. 新增确定性累计检查器 `ar2-7e-cumulative-closure.py`，只读取已提交 JSON/Markdown、产品文件哈希和 Git 文件清单，输出 `ar2-7e-cumulative-closure.json`。
2. 检查器必须证明：37/37 与 24/24 总矩阵通过；八个富交互专项均 PASS 且覆盖三视口；所有请求/租户/页面/控制台错误与禁止副作用计数为零；产品哈希未漂移；所需方案、机器证据、截图与验证文档均由 Git 跟踪。
3. 以当前最终证据做一次 Prime 独立增量只读审查，输出只允许写入审查结论摘要，不允许 Prime 修改代码、authority 或仓库文件。
4. 更新 `closure-manifest.md` 与 `dynamic-reference-phases.json`：登记 7E 累计证据和唯一退出标记；保持 AR2 fixture 与 A0-V 真实只读边界。
5. 复跑累计检查器、`verify_closure.py --phase ar2-7`、相关 Web 测试和生产构建；对照方案复核风险与无副作用计数。
6. 先提交 AOS 累计闭合证据，再以该提交作为 Delivery Receipt 输入，通过共享记忆 CAS 将同一 AR2-7 Task/Lease 推进到下一 revision；不得手工伪造 authority。
7. 回读 authority、01/06 投影、Receipt、事件和 memory gate；最终验证文档记录 AOS 提交、文档提交、revision、测试和边界。

## 4. 退出条件

- 7D + 7E 所有累计条件通过，`verify_closure.py --phase ar2-7` 五类错误集为空。
- Prime 增量只读审查首行 `VERDICT: PASS`，且明确 fixture、OAuth、本地辅助和无业务副作用边界。
- Web 定向/全量测试与生产构建通过；确定性累计检查器 PASS。
- 同一 Task/Lease 形成唯一最终 Delivery Receipt，authority CAS 成功并可回读。
- 仅在上述条件全部满足后写入唯一退出标记，并把下一安全阶段登记为 A0-V；此标记不代表 A0-V、八个真实业务场景或发布完成。

## 5. 停止规则

任何必需证据缺失、Git 漂移、Prime 非 PASS、测试失败、closure 错误、CAS 冲突、租户漂移或副作用非零时立即停止最终标记与 authority 前推。只修复已定位的最小问题并从对应门重新验证，不重复业务命令，不扩大授权。
