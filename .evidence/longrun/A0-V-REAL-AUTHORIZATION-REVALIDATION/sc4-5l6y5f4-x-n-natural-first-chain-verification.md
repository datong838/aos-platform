# SC4-5L6Y5F4 X：N 自然商品首链验证

日期：2026-09-17

## 已完成控制面

- W 后继 N 身份保持为 installation `d42cd39a-bc44-403b-a184-c241cae7769e`、generation `677046ff-6147-4b3b-905d-9e12964b6581`、execution epoch 3；Runtime Host 仅加载 N。
- N SourceSelection 首建 revision1，hash `sha256:30a3e52bee1039a966ac128697a4281e8afd2faeb928931ea39ad420038e02f7`；RuntimeControl 首建 revision1，hash `sha256:b1945509b1937b86d0e2333c22ab576374664470706b06192029a22d62f588bc`。
- schedule control binding 从 L revision15 精确继承为 revision16，hash `sha256:d5d49ce2751b9355f40a7a67203de28517a7d56aaab29a0d6ef613625d7cf0f8`。
- Policy10 经独立审批写入，hash `sha256:3787b835eafc04830767b1cbcb92acfa6eceeb035eda0562f3dd5c326956d9e4`，Policy 本体仍 disabled；EventPolicyControlReceipt `ccd903fc-988e-51fa-8eae-7b3ff11c061b` revision1 只启用 N 的 automation binding。
- 九条 N 业务路由加 `ecommerce_growth_event_control` 共十条，从 group42 原子扩为 group43；所有路由仍指向同一 N generation/epoch，operation fence=false。
- 02:21:13 CST 武装既有整点 Cron。武装读回为 enabled，Policy10 binding revision1/effectiveUntil 03:49:14 CST；窗口内初始 run/ingress/occurrence/investigation Run 全空，inflight running/unresolved 均 0，负租户 dispatch 为 0。

## 纠偏与恢复

第一次 v3 selection 错误引用了 L selection revision2。Owner 因 predecessor 非 N 当前值而拒绝，事务无写入；失败 intent 保留。代码与方案改为 v4：按 installation/generation 隔离的 selection/control 在 N 首建时 previousRef 为空，只有按 schedule 延续的 binding 引用 L revision15。v4 四阶段全部成功。

原 watch 的 2280 秒边界会在 02:59 左右早于 03:00 Cron 退出。观察器尚未见任何 run/ingress 时被停止，schedule 未关闭、未重新 arm；默认上限修为 3300 秒并完成只读状态复核后重启。此修复不更换业务 key、不产生第二个 arm intent，最长 running 延展仍早于 authority 到期。

## 验证

- `test_a0v_n_product_window.py`、`test_a0v_n_successor_business.py`、`test_a0v_qyh_current_product_event_first_chain.py`：20 passed。
- timeout 边界修复后定向测试：2 passed。
- 证据 JSON：authority selection/control/binding、Policy10 put/enable、route expand、natural arm 均存于同目录 `sc4-5l6y5f4-x-*.json`；原始命令输出保留为 `*-raw.log`。

## 自然业务终态

X **未宣绿**。03:00 CST 唯一 Cron `scr-304a30c952564b38` 自然运行成功，写入 65 行；真实 ingress source revision `a84b6c79-8654-48f0-98c2-57d41b067b3d`、envelope hash `15b3c65a8b2eff01ccab97b5e3cca0796d435b7b595baf5e10e616f23566571e`，投影 outbox 65 条。worker 自然发现候选，但消费返回 `ValueError`，occurrence、attempt、investigation Run 均为 0。schedule 于 03:03 前禁用，无第二 source run，canary 0、inflight/unresolved 0。

用相同 Policy10 参数和 65 条权威 outbox 元数据直接执行已签名 core 1.4.0 纯窗口函数，65 条全部成功，故拒绝位于 Host 当前权威/提交链，而不是源读取或纯窗口计算。原日志只保留异常类型，已按方案补安全限长诊断文本并通过回归；为加载新日志而优雅停止 Host 后，N 按既有失败恢复规则进入 binding revision7/epoch4、enabled=false、fenced=true、observed=unknown。该代不可原地复活，未尝试改表解除栅栏。新 Host PID14560 为空目录、canary0，等待正式后继代。

终态证据为 `sc4-5l6y5f4-x-final-diagnostic.json` 与 `sc4-5l6y5f4-x-natural-disarm.json`。X 已真实证明 `source → ingress`，也真实暴露 `ingress → occurrence` 缺口；不能据此勾选 Case/Run 或经营闭环。

## 下一波

X 失败，下一波先按既有不可原地复活规则创建干净后继 O，并在新 Host 加载安全诊断版本；N 保持 fenced。O 重建当前 SourceSelection/Control、Policy11 与路由后等下一自然 Cron，禁止复用或改写 N 的 ingress。只有 O 形成 occurrence/Case/Run 后才进入来源化建议和 exact 经营计划评审。人工评审后的内部内容任务、真模型产物、续跑、总控复盘/Wiki 与八工作台连续观察仍是后继业务验收，不能由本波控制面替代。
