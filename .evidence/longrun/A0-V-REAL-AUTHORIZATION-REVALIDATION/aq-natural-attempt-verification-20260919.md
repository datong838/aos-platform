# AQ 自然 attempt 失败边界与 strict link 写入修复验证

## 自然执行终态

- AQ installation：`d6839bf3-55b5-474c-aa21-49966e15db3d`
- generation：`b31be2a7-36fd-4348-9ff8-10939cc3d1cd`
- 唯一自然 attempt：`16ca3c76-4dbe-48c3-9ff3-4f06eb9fbc82`
- accepted：`2026-09-19T06:35:52.282194Z`
- completed：`2026-09-19T06:41:22.956400Z`
- terminal：`RECOVERABLE_INGRESS_DEADLINE_EXCEEDED / IngressJournalConflict`
- attempt count：1；没有手工 `run_definition`，没有重发未知结果。

Attempt 终结后仍为 12 Run running、12 Dataset Receipt、1 relationship assessment、1 Link Command（1168
links）；Retirement、Store Receipt、`ecom_link`、link outbox、projection pending 均为 0。`dev-org/dev-project`
canary 为 0，证明失败事务没有越过 Store 提交边界。

qcursor 在终态后立即停止。只读 Guard 再次确认上述精确事实后，`pause-failed` 以 idempotency key
`a0v-aq-saved-snapshot-pause-failed-v1` 将 definition rev65 enabled 推进为 rev66 disabled；AQ 不再具备自然重跑入口。

## 根因与修改

前一轮 strict-link 优化只把端点与已有 link 的读取/锁定批量化。真实 SSH 数据库仍需逐条执行 1168 次
link 写入、1168 次 sequence nextval 和 1168 次 outbox 写入，数千次远端往返耗尽 300 秒；同步 Store
调用返回后才触发 deadline 检查，因此外层只记录 `_check_active`。

本轮在同一 strict transaction、同一完整锁定快照内先做全部版本/载荷/墓碑/dangling 判定，再批量写 link、
批量取得 projection revision、批量写 outbox。Receipt、checkpoint CAS、request hash、事务内精确事件复核、
RLS 与 retirement 前置条件保持不变；retirement 原载荷校验复用相同锁定快照，不再逐 link 重读；普通
batch 保持原路径。

## 验证

- `test_ecom_consistency_store.py`：64 passed；
- 隔离 PostgreSQL 1168 strict links：1 passed，整项 5.70 秒，终态 link=1168、Receipt=1、outbox=1168，
  精确 replay 成功；
- group link + retirement 隔离 PostgreSQL：14 passed / 118.30 秒；
- AQ attempt guard + saved recovery：14 passed；
- Python compile 与 `git diff --check` 通过。

曾将完整 Store 与 AQ Guard 两套 PostgreSQL 会话并行启动，迁移对全局 `aos_runtime` role 的同时 ALTER
触发仓库已知 `tuple concurrently updated`，测试体未执行。停止并发后串行重跑，以上项目全部通过；没有
触发产品业务写入。

## 浏览器与运行边界

8434 的“本体管理（数字孪生）”可加载，显示 AOS v1.6.5、缓存对象与写队列 0。页面同时明确显示
“当前离线 / aos-api health 500”，这是 qcursor/API 按失败冻结规则停止后的预期边界；不能据此宣称系统在线
或电商工作台已恢复。

## 下一波

按正式生命周期退休 AQ：停用/释放 runtime binding，恢复九路由到 fenced legacy 并核对 3 resources、
Attempt、Receipt、canary。随后提交并重载包含本轮批量写修复的 Runtime Host，建立 AR direct successor，
转移同一 saved snapshot，等待唯一自然 attempt。只有严格 Store、投影、12 Run 与 retirement 全部闭环后，
才进入经营参谋 Policy v3 自然首链。
