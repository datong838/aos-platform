# AR2-7E 任务总控非空隔离功能验收方案

日期：2026-09-10  
分支：`m1`  
基线：`3ce46abe`  
权威：`AOS-000572 / AR2_7D_RUNTIME_WIRING_CANONICAL_ROUTER_GREEN`  
状态：执行器编码前冻结

## 1. Rules 与目标

- 本切片承接 231-6 第 161、181、201～207 条与 closure manifest 的新边界：7E 使用不含真实凭据、客户数据和经营结果的合同 fixture；真实只读经营数据留给 A0-V/A1。
- 在 `m1` 串行验证任务总控的非空隔离路径：经营参谋推荐回填、两步确认创建内部 Task、刷新回读、六数字同事浮层、十共享能力入口、复盘三段、底部双栏、明日预告、状态筛选、日历与三视口。
- 唯一允许的写请求是 Playwright 路由内截获的 `/api/v1/aip/tasks` 隔离 Task fixture；它不抵达后端、不写数据库、不调用 Provider、不产生费用或外部副作用。第一次“下达”只能完成安全预检，第二次确认才产生一个 fixture Receipt；同一幂等键不得产生第二个任务。
- 所有 Workshop 请求仍须为 GET；其余 POST 一律拒绝。真实租户 mutation、发布、迁移、push 和 `230 L0` 均保持关闭。
- 同一视口连续失败两次即停止；先定位合同或控件根因，不弱化断言。

## 2. 计划新增文件

- 执行器：`.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/ar2-7e-task-cockpit-rich-browser.mjs`
- 机器证据：同目录 `ar2-7e-task-cockpit-rich-browser.json`
- 截图：同目录 `ar2-7e-task-cockpit-rich-{width}x{height}.png`
- 验证说明：同目录 `ar2-7e-task-cockpit-rich-browser-verification.md`

不预设产品源码修改。若浏览器发现产品缺陷，先另写缺口方案，再按 RED→最小修复→回归处理。

## 3. 固定三视口动作

每个独立 context 在 `1280×720`、`1440×900`、`1920×1080` 执行：

1. 读取非空 Task、Analyst exact metrics、十项 Capability、最小 Agent/Skill 链和复盘治理数据。
2. 点击第一条经营参谋推荐，验证文本与 exact source 引用回填；第一次点击下达只出现安全预检且 POST=0。
3. 第二次点击确认，截获唯一 `/api/v1/aip/tasks` POST，核对中文业务标题、固定类型、角色建议、sourceEvidence、Idempotency-Key；返回版本化 Task，随后总控 GET 回读同一 taskId，页面显示受理成功与已回读。
4. 逐一打开并关闭六个数字同事浮层；逐一打开并关闭十个共享能力详情，核对浮层无越界遮挡。
5. 切换状态筛选后恢复；打开任务日历后返回；核对今日复盘、AI 改进建议、Wiki 今日入库三段、执行/策划双栏与明日预告。
6. 折叠/恢复侧栏，滚动到页面末尾；验证八项 Workshop 菜单、唯一 H1、无水平溢出、无 page/console error。

## 4. 退出条件

- 3/3 单元 PASS；每单元六同事、十能力、三复盘、双栏、明日预告、日历、状态筛选均有机器读数。
- 每单元 `taskPosts=1`、`preflightPosts=0`、`readbackMatched=true`、Workshop 非 GET=0、其他写请求=0；无未知 GET、租户漂移、5xx、page/console error或水平溢出。
- 专项测试、Web 累计、production build、`verify_closure.py --phase ar2-7`、`git diff --check` 全部 GREEN。
- 该切片通过后继续其余七页非空/按钮/刷新/回读矩阵，不前推 7E authority。
