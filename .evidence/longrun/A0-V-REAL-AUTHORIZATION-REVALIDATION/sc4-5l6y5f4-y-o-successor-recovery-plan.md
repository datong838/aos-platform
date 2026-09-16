# SC4-5L6Y5F4 Y：N 失败收口与 O 后继恢复方案

日期：2026-09-17

## 起点

X 的自然 Cron `scr-304a30c952564b38` 已成功形成 65 行真实 ingress，但 event consumer 在 occurrence 前失败。schedule 已禁用，Policy10 automation binding revision1 仍 enabled；十路仍为 N extension/unfenced group43。诊断重启使 N runtime binding 进入 revision7/epoch4、enabled=false、fenced=true、desired=enabled、observed=unknown，三资源 released；新 Host PID14560 active 但目录为空。N 不可原地复活。

## 固定顺序

1. 事实预检：锁定 N installation/generation、released binding7、Policy10 binding1、十路 group43、唯一 X run/ingress、零 occurrence/attempt/inflight/canary、schedule disabled。
2. 事件入口收口：ReleasedProductEventControlService 以 N runtime7/route epoch3 禁用 Policy10，binding1→2；独立审批后 fence event-control，group43→44；排空后 shrink，group44→45，只留九条 N 业务路由。
3. N 正式退役：复用现有 released-owner settlement，生成独立 disable operation；由 Host/原 consumer 完成 desired=disabled 与九路 disable/detach，必须得到正式 fence/detach Receipt，路由转 legacy/fenced。未知结果只读 operation/Receipt，不重发。
4. O 安装：以上一步 N exact replacement ref 创建新 approved O；创建前固定校验 N binding revision9/epoch5/desired=disabled、九路 legacy/fenced group47、Policy10 disabled 和零 inflight/canary。O approved revision3 且无 binding 后，使用 N etag5 正式卸载 N；随后依次 prepare/verify/stage/configure/enable。O 必须最终为 active revision5，唯一 binding revision4/epoch3、enabled/ready/unfenced，三项资源均 pending 且 Host 只有 O 一个 live target；每阶段使用 O 专属目录和新幂等键。
5. O successor 登记与切流：精确引用 N detach Receipt，九路 legacy group 建立 successor registration；独立 cutover approve/prepare/pause/commit/validate/resume，使九路只指向 O，Policy10 与 source schedule 保持 disabled。
6. O 自然首链：建立 O 首版 SourceSelection/Control、新 schedule binding、Policy11 和 event-control 路由；等待下一整点真实 Cron。禁止复用或改写 N ingress，禁止人工 POST run。诊断日志须能给出受控拒绝明细；成功则继续 Case/Run，失败则按同一新 run 收口。

## 文件范围

- 新增 `scripts/a0v_o_recovery.py`，先实现第 1–4 步；登记/切流及自然窗口按实际 O identity 另增固定 profile。
- 复用 `a0v_m_reinstall_recovery.py`、正式 installation/runtime/configuration Owner，不修改历史 N intent/result。
- 新增 `services/aos-api/tests/extension_runtime/test_a0v_o_recovery.py` 与本目录 Y 证据。

## 停止条件

任一 X run/ingress、N binding、Policy10、group43、inflight、canary、Host 或 Receipt 漂移即停止。N 没有正式 detach Receipt不得创建 successor registration；O 未 ready 不得切流；切流未完成不得启用真实 source。禁止 SQL 改状态、复活 N、删除失败证据或以新代冒充 N 原 run 的恢复。

## 第 4 步实况修订（03:39 CST）

O 已按 replacement ref 创建，N 随后正式卸载；O apply 成功，但 verify 被 `guard_replacement_activation_in_transaction` 拒绝，因为 immutable O lock 要求 N 在激活时仍保有 active baseline。Host fail-closed 退出，O 停在 applied revision4，verify accepted，三资源 released，九路仍 legacy/fenced，零业务副作用。该顺序不能继续，也不得修改 lock 或复活 N。

采用既有 preparation-reset 正式恢复分支：等待 O verify deadline 到期后 reset 到 approved revision5，使 accepted verify 终态化；创建无 predecessor 的干净 P（记录 interrupted O），P approved 后卸载 O，再对 P 执行 prepare/verify/stage/configure/enable。最终约束改为 P active revision5、binding revision4/epoch3、enabled/ready/unfenced、三资源 pending、Host 唯一 live target=P。后续第 5、6 步以 P 为 successor，不再以 O 为目标；O 失败记录永久保留。

## 第 5 步固定输入

P=`9950e057-5cb4-4849-a499-35837d8d0fb6`，generation=`df883b18-0170-410b-8424-442c7cdd60b4`，lock=`sha256:15ac55d0ca7098c4df286ad70b6a20e79c327b0ec9c53baceea7cbb7059fcae8`，config=`31cebe73-d50e-43dc-8165-7e94ab3409f2@1` / `sha256:20183377bbe9a528104fe009eda106f768c9213ef8c20e40c9a0976d396dbce1`。N revision6/uninstalled；N detach Receipt=`4d075823-2066-4706-9f25-542dff38bba2` / `sha256:279923c2997b4221c348576e1079a8d8fe7fdeae860df002fe132c2c3214acad`。九路必须保持 legacy/fenced、route revision26、group47，零 inflight/canary。登记后仍不改路由；切流依次 approve/prepare/pause/commit/validate/resume，目标 group48，九路指向 P epoch3，且 Policy10/source schedule 仍 disabled。

## 第 6 步实况与失败窗口收口（04:00 CST）

P Policy11 与 event-control 扩容完成后，source schedule 仅在 03:54–04:01 打开。
04:00 自然 Cron `scr-4eda5462575a4740` 成功读取真实源并写入 65 行，形成 65 个
P/epoch3 occurrence；未人工 POST Run。第一个至第三个 occurrence 在创建分析 Run 时
被 `BusinessInvestigationRunConflict` 拒绝，随后两个在 schedule 禁用后的来源复验中被
`PermissionError` 拒绝。五个 attempt 均为 unknown/needs_attention，另外 60 个保持
pending，零 InvestigationRun、零 canary、零外部效果。达到同阶段重复失败停止条件后，
source schedule 已禁用且 Host 已停止。

根因事实是旧自然 occurrence `37bead7a-52d6-5e6e-878e-a8e1e54a294c` 已留下
`analysis-e5b19a5fe290ce1bf60d5038cb1d6cf6` 的唯一 active slot；它仍为
PREPARING/RUNNING，绑定 Case revision9。P 当前 Case 已到 revision13。BIW4-003 正确
拒绝把新的 recovery trigger 合并到非 scheduled 的活动 Run；不得删除 slot、改 SQL
状态或把新 occurrence 冒充旧 Run 的重放。

本波只做耐久收口：使用当前 Case13、Policy11、P binding revision6/epoch3 和 group49
形成独立审批，先以正式 event-control 命令把 automation binding revision1 禁用，再把
event-control 路由 group49→50 fence。保留该路由成员而不 shrink，保留全部 65 个
occurrence 和五个 unknown attempt。退出条件为 schedule disabled、Policy11 binding
disabled、event-control fenced、Host stopped、零 running/canary，且不再增加 attempt。

下一波 Z 只读核对旧 active Run 的 Task/Plan/Checkpoint/DataRequirement/统一 Receipt
与五个 unknown attempt，先决定“续跑旧 Run”或“正式终止旧 Run 后接当前 pending”这
一个权威分支；不得重新读源、重新生成 occurrence 或恢复 Host。方案和测试完成后才允许
处理既有 65 个 occurrence。

### 停机后的运行态修订（04:05 CST）

停止 Host 会按原资源日志释放 P 的三个短租约，并把 runtime binding 推进为
revision7/epoch4、enabled=false、fenced=true、desired=enabled、observed=unknown；这是
正确的不可原地复活状态。原计划中的普通 event-control disable 因而在 Host Port
revalidate 前被 `runtime binding is not executable` 拒绝，事务没有生成控制 Receipt，
Policy11 binding 保持 revision1/enabled。该失败 intent 与原始错误永久保留，不重发。

此时 event-control 路由虽仍为 group49/unfenced，但 runtime binding 的 epoch/fence 已使
所有 claim fail-closed；schedule disabled、Host stopped，attempt 数稳定为五。因 released
专用 disable 正确要求先清零 unknown，而 unaccepted closure 又要求正式 fence Receipt，
不得绕过形成顺序。Y 以“耐久无执行、待 Z 正式退役”收口，不伪称 Policy11 disabled。
Z 必须先设计 P 的 unknown-preserving 正式 disable/detach 与 unaccepted closure 顺序，
并评估旧 active Run 的续跑/终止；若 P 不可恢复，则建立 Q 且不得把 P occurrence 改绑。
