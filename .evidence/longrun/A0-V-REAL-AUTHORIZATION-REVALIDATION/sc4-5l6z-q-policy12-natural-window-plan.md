# SC4-5L6Z-Q｜Q Policy12 与真实自然窗口方案

日期：2026-09-17。基线：`89185206`。本方案承接 Q 干净继任，仅恢复栖月汇真实只读商品变化链；商城源库写入、人工建 Case/Occurrence、外部发布和 230 L0 均不在授权面内。

## 1. 当前事实

- Q=`9c49b383-e04d-41b4-8276-8b8bc6db49a8`，generation=`98aea676-ee71-4d42-a6c8-6634960efe5e`，config=`235146cc-26a2-44e7-a39e-8b20904f1776@1`；当前 binding6/epoch3/ready/enabled。
- 九业务入口已由正式 cutover 指向 Q，route30/group54；可选 `ecommerce_growth_event_control` 尚不存在。
- P Policy11 的不可变 policy hash 为 `sha256:225d22ed09f209b9b6444bbc896bf958049b90fee7889da8c607df5f22327de5`，其执行 binding 已 revision2/disabled；P 65 个 occurrence 已 cancelled，不能迁移或复用。
- 最新 source control binding 为 revision17/hash `sha256:83758e3c663c6f4b06946c6d09c4b70abd338158ea6d9535ca7467f8ba0796ad`。source schedule 为 disabled，last_run 为真实 Cron `scr-4eda5462575a4740`。

## 2. 实施

1. Q preflight 固定 Q create/result、cutover resume Receipt、binding6/config/签名根，并要求计划停用、无未决执行。
2. 新建 Q SourceSelection、RuntimeControl 与 schedule control binding revision18，精确引用 revision17；这一步不启动 schedule。
3. 以 P Policy11 为 priorRef 生成 Policy12 与 Case14，经 exact AIP 审批后从 Q canonical router 保存。
4. 对 event-control 独立审批，将第十路由按 group54→55 expand；再对 Policy12 control 独立审批并建立 binding1/enabled。所有动作写前冻结 intent，已有 intent 只读核验，不盲重发。
5. 计划仅在一个有界窗口内启用，等待自然 Cron；只允许真实只读 Niushop 商品源。窗口结束立即停用并读回权威 cursor。
6. 对账同一 source revision/run 的 ingress、ProductEvent、Occurrence、Case/Run 与后续数字同事节点；若没有真实变化，记录合法空窗并等待下一窗口，不造数。

## 3. 退出/停止条件

- Policy12、Case14、control binding18、event expand group55 和 Policy12 enable 均有不可变 Receipt；Q 四元组一致，P 保持终态。
- 窗口前后 source schedule 可证明停用；最多一个新 source call，不出现跨租户、重复 command Receipt、unknown attempt 或外部副作用。
- 任一签名、priorRef、Case version、group/binding revision、Host target 或 cursor 漂移，停止写路径并只读核验。

## 4. 文件清单

| 文件 | 动作 | preHash / 边界 |
|---|---|---|
| `scripts/a0v_q_product_preflight.py` | 新增 | 基于 P preflight `ba5826...`；固定 Q resume/binding6 |
| `scripts/a0v_q_product_window.py` | 新增 | 基于 P window `24a666...`；authority18、Policy12、group54 |
| `services/aos-api/tests/extension_runtime/test_a0v_q_product_window.py` | 新增 | priorRef、Q 目标、revision/group 拒绝测试 |
| `scripts/a0v_q_natural_product_event.py` | 新增 | 后续有界启停与自然观察；不手工触发 run |
| `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/sc4-5l6z-q-policy12-natural-window-*` | 新增 | 逐阶段和自然链对账证据 |

通用 authority/policy/enable 服务脚本保持不改，分别为 `9a39ac...`、`f788ba...`、`807945...`。
