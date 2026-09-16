# SC4-5L6Z-Q｜P 正式终结后的 Q 干净继任方案

日期：2026-09-17。基线：`f3570ece`。本切片继续 231/BG-02 的 A0-V 真实首链恢复，不扩大 230 L0 权限，不允许商城写副作用。

## 1. 权威前置事实

- P installation `9950e057-5cb4-4849-a499-35837d8d0fb6` 已为 `uninstalled@6`；runtime binding 已为 revision 10 / epoch 5 / desired `uninstalled` / observed `stopped`，三资源全部 released。
- P disable operation `92809daf-2988-421f-a2f5-dece5bdb75e3` 已成功，detach Receipt 为 `b2297c08-f8a2-45c3-9f5c-60a66040a1c8`，hash `sha256:19b589d3468a3f56cc02452531cf868111391beb4b04556fda38862350ec8de4`。
- 九条业务入口均为 legacy / fenced / route revision 29 / group revision 53；零 running execution、零 claimed/unknown dispatch、`dev-org/dev-project` canary 为零。
- 栖月汇计划保持 disabled；权威 `last_run` 已恢复到真实 Cron 成功运行。Q 启用和切流阶段不得启动 source schedule。

## 2. 实现顺序

1. 新增固定 Q 生命周期执行器。每个写动作前复核 P 终态、P detach Receipt、九路由快照、零未决与 canary；Q 使用当前签名包版本 core 1.4 / niushop 1.23 / growth 1.10 / operations 1.2 创建独立 approved installation，不传已卸载 P 为 active predecessor。
2. Q 按正式 prepare → verify → stage → configure → enable 顺序建立独立 generation/config/epoch。每阶段使用不可变 intent/result；结果未知时只读回，禁止重发。
3. 新增 Q successor registration。请求必须精确引用 P detach Receipt、Q `active@5`、binding `4/epoch3/ready` 和九路 group 53；登记只生成 Receipt，不改变路由。
4. 新增 Q 独立 cutover approve → prepare → pause → commit → validate → resume。目标仍为九条业务入口，不含 event-control；成功后九路必须只指向 Q，group revision 54，计划继续 disabled。
5. 下一波再建立 Policy12、可选 event-control 路由和一次有界真实只读自然窗口；不得用手工 Case、旧 P occurrence 或源库造数代替自然触发。

## 3. 退出与停止条件

- Q 安装、配置、登记和切流均有正式 Receipt，且 installation/generation/epoch/config 四元组一致。
- 九路切换前保持 legacy/fenced；切换后只指向 Q 且 unfenced。P/O/N 等历史安装不可复活、不可改写。
- source schedule 全程 disabled；外部副作用 0；租户 canary 0；未决 runtime/dispatch 0。
- 任一主库版本、Receipt hash、资源状态或进程所有权漂移，立即停止该写路径并只读核验；同一 phase 不盲重试。

## 4. 计划文件清单

| 文件 | 动作 | preHash / 边界 |
|---|---|---|
| `scripts/a0v_q_clean_successor.py` | 新增 | Q 安装和五阶段 lifecycle；不启动 schedule、不调用商城写接口 |
| `scripts/a0v_q_successor_business.py` | 新增 | 固定 P detach + group53 + Q 当前状态的登记入口 |
| `scripts/a0v_q_successor_cutover.py` | 新增 | Q 独立审批与六阶段切换；九业务入口限定 |
| `services/aos-api/tests/extension_runtime/test_a0v_q_clean_successor.py` | 新增 | P 终态、Q 创建及阶段拒绝回归 |
| `services/aos-api/tests/extension_runtime/test_a0v_q_successor_business.py` | 新增 | Receipt/hash/group/tenant/代次拒绝回归 |
| `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/sc4-5l6z-q-clean-successor-*` | 新增 | 方案、逐阶段结果、验证与风险 |

复用文件仅作已验证基线，不修改：`scripts/a0v_o_recovery.py`（`11ffa5...`）、`scripts/a0v_p_successor_business.py`（`96963c...`）、`scripts/a0v_p_successor_cutover.py`（`5841c9...`）、`scripts/a0v_ecommerce_transaction_reinstall.py`（`08daa2...`）。
