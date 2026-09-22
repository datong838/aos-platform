# DC 正式退休与 DD direct successor 方案（2026-09-22）

## 上位方案复习

- 上一波 `04afe49d` 已冻结 DC saved-snapshot：**rev4** `IngressJournalConflict` 边界；
  definition **229** disabled；唯一 attempt `6092d972-5734-44f1-abe4-56020afb2b4d`。
- BG-00 字母链下一环：DC 正式退休 → DD direct successor →（封板后）DD saved-snapshot。
- 租户 `org-org/dev-project`；无商城源读、无 `run_definition`；本波无页面改动（浏览器验收 N/A）。

## 本波文件级清单（6/6 对应）

| 步 | 路径 | 动作 |
|---|---|---|
| 1 | `.evidence/.../dd-direct-successor-plan-20260922.md` | 本方案 |
| 2 | `scripts/a0v_dc_terminal_retirement.py` | DC released 退休 overlay |
| 3 | `scripts/a0v_dd_replacement_recovery.py` | 绑定 DC detach Receipt |
| 3 | `scripts/a0v_dd_successor_business.py` | prepare→enable |
| 4 | `scripts/a0v_dd_successor_cutover.py` | 九路 cutover |
| 5 | `scripts/a0v_dd_health_observation.py` | 只读 +12 观察 |
| 6 | `.evidence/.../dd-direct-successor-verification-20260922.md` | 终态验证 |
| 6 | `services/aos-api/tests/.../test_a0v_bn_saved_snapshot_recovery.py` | overlay 断言 |
| — | `docs/palantier/.../memory/leases.json` | **不**进本波 commit |

## 当前权威（执行前）

- HEAD `04afe49d`；DC `02d39eb8-174e-432f-9776-57de7c4436c8` / `bd59503f-eb9e-4fe6-a09d-a92a3b924682`，
  九路 **288/315**，binding rev6/epoch3，唯一 Host **51083**。
- definition **229** disabled；recovery **75**；failed attempt 见上。
- 12/12、Store=0、`ecom_link`=0、canary=0。

## 串行步骤 1-6

1. **plan/preflight**：本文件 + m1 单写者、Host/worker/18181 计数。
2. **DC 退休**：SIGTERM Host 51083 → released retirement；目标 legacy **290/317**；
   preflight 前不得 mkdir `replacement-dd`。
3. **DD lifecycle**：仅 DC detach Receipt；RuntimePolicy rev11；唯一 Host。
4. **注册与 cutover**：新 OPERATION UUID；目标九路 **291/318**（相对 288/315 的 successor 惯例 +3/+3 以 cutover 读回为准）。
5. **健康观察**：live baseline，delta +12；不重发已知 freeze。
6. **verification/commit**：专项 pytest + 累计 `-k dd_`；提交 8 文件；自动 **DD saved-snapshot**。

## 停止条件

identity/Receipt/hash/revision 漂移、第二 Host/worker、未知重发 → fail closed。不 push；不改 w2-workshop。
