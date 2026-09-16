# SC4-5L6Y5F4 Y：P 自然窗口恢复与受控停机证据

日期：2026-09-17

## 结论

本波完成 N 正式退役、失败 O 的不可变收口、干净 P 安装、九路 successor 登记与切流，
并为 P 建立 Policy11 与 event-control 第十路。04:00 的真实 Cron
`scr-4eda5462575a4740` 在 `org-org/dev-project` 自然执行成功，写入 65 行真实 ingress，
随后自动产生 65 个 P/epoch3 occurrence。这证明真实数据更新已经无需开发者手工 POST
即可进入 occurrence 层，比 X 波“只到 ingress”前进一层。

首个分析初始化没有继续：系统中仍存在旧 occurrence
`37bead7a-52d6-5e6e-878e-a8e1e54a294c` 创建的唯一活动 Run
`analysis-e5b19a5fe290ce1bf60d5038cb1d6cf6`，其状态为 PREPARING/RUNNING、Case
revision9；P 当前 Case 为 revision13。BIW4-003 的单活动 Run 守卫正确拒绝新的 recovery
trigger。前三个 occurrence 因 `BusinessInvestigationRunConflict` 进入 needs_attention，
schedule 禁用后又有两个在来源复验处被拒绝；共五个 unknown attempt、60 个 pending，
没有生成新的 InvestigationRun、没有 canary、没有外部效果。

达到重复失败停止条件后，source schedule 已禁用，Runtime Host 已停止并确认
`RUNTIME_HOST_STOPPED`。P 三个资源均正式 released，runtime binding 为
revision7/epoch4、disabled/fenced/unknown。普通 event-control disable 在 Host Port
revalidate 前失败，控制 Receipt 数为零；对应 intent 和错误原样保留，未重发。Policy11
binding 仍为 revision1/enabled，但 released runtime fence 使其不可执行。十路仍为
group49，attempt 数已稳定。

## 关键权威

- N detach Receipt：`4d075823-2066-4706-9f25-542dff38bba2`。
- P installation：`9950e057-5cb4-4849-a499-35837d8d0fb6`。
- P generation：`df883b18-0170-410b-8424-442c7cdd60b4`。
- P successor registration Receipt：`004f70a2-1b72-4125-af85-77fa2420ac5a`。
- P cutover operation：`0bd6a2c7-fc35-5c64-bfed-534eb88c9d74`。
- 自然 source revision：`a84b6c79-8654-48f0-98c2-57d41b067b3d`。
- 自然 ingress envelope：`e75d9e3a42bb0df0267b1b4be3dd4efe8a3ed7d116eea56140114a9fbb3d7127`。
- 最终事实快照：`sc4-5l6y5f4-y-final-snapshot.json`。

## 代码与验证

新增固定恢复/切流/窗口脚本：

- `scripts/a0v_o_recovery.py`
- `scripts/a0v_p_successor_business.py`
- `scripts/a0v_p_successor_cutover.py`
- `scripts/a0v_p_product_preflight.py`
- `scripts/a0v_p_product_window.py`
- `scripts/a0v_p_natural_product_event.py`
- `scripts/a0v_p_failed_window_containment.py`

新增测试位于 `services/aos-api/tests/extension_runtime/` 下对应
`test_a0v_o_recovery.py`、`test_a0v_p_successor_business.py`、
`test_a0v_p_product_window.py`、`test_a0v_p_failed_window_containment.py`。

- O/P 定向测试：10 passed。
- M/N/O/P 累计恢复测试：25 passed。
- P 收口与邻接测试：8 passed。
- 全部新增脚本 `py_compile` 通过；`git diff --check` 通过。
- AR2 ar2-7：1982 scanned / 199 classified / 93 migrated；五类错误为空。
- 闭包清册仅追加此前已提交 Host 事务门
  `ecommerce_event_proposal_gate.py` 的真实职责与初始 hash，不改历史 preHash。

## 已知边界与下一波

`meta_schedule_run` 与 ingress 权威保存了 04:00 Cron，但 schedule PATCH 后
`meta_schedule.last_run` 投影仍显示旧 manual run；下一波应登记并修复该投影保真问题，
不得用它否定不可变 Run/ingress。

下一波 Z 先形成 P unknown-preserving 退役与旧 active Run 对账方案。必须核对旧 Run 的
Task、Plan、Checkpoint、DataRequirement、统一 Receipt 与五个 unknown attempt，选择
“续跑旧 Run”或“正式终止旧 Run”这一条权威路径。若 P 已不可恢复，则正式关闭 P 的
未接受 occurrence 并建立 Q；不得改绑 P occurrence、删除 active slot、重发未知结果或
人工制造新 Run。之后才恢复自然首链，并继续 exact 评审、内容任务、多媒体产物、人工
评审续跑、复盘/Wiki、八工作台真实场景和连续观察。
