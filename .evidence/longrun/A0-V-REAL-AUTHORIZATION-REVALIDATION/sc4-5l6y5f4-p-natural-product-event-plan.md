# Y5f4-P L 真实商品变化自然触发入口恢复方案

日期：2026-09-16

基线：m1 `f5f81d62`

## 目标

从 L 已完成 successor 九路切换、event-control 已正式 shrink、真实商品源 schedule 与 revision 7 policy/binding 均关闭的状态，重新建立 L 专属的可追溯入口，并让 `0 * * * *` 的真实 Cron 自然读取栖月汇商城商品数据。禁止通过 POST run 或开发者手工造 Case 代替自然触发；数据变化若满足策略，应由 ingress/outbox/worker 自然形成 occurrence、Case/Run 接续。

## 权威基线

- L installation `19620ea4-4a36-4cf1-a14a-8b24ee7d9fc3`，generation `64742c68-5e71-485b-a3c8-edc20be3d101`，runtime binding revision 6 / epoch 3 / ready。
- 九路均为 L extension，route revision 21 / group revision 36；event-control 行不存在。
- schedule `sch-p02-qyh-controlled-20260913-v1` 对应 `P02-product-qyh`、`niushop-qyh`，cron `0 * * * *`，当前 disabled；最近真实运行 succeeded、rowsWritten=65。
- policy `product-event-qyh-full-store-generation-f-20260916` 当前 revision 7、disabled；旧六条 binding 全部 disabled 且过期。
- 当前 Case `case-qyh-full-store-baseline-20260915` 保留为经营对象；新 revision 8 只续接来源/安装代际，不新造 Case。
- Runtime Host 唯一正租户运行，零 canary、零 inflight；外部副作用继续关闭。

## 固定阶段

1. preflight：只读校验 L cutover Resume Receipt、签名 Niushop 1.23 包、P02 图、source configuration、mapping/schema/masking、当前商城连通性、角色/预算/配置、九路、schedule/policy/binding 和零 inflight；授权窗口覆盖下一个整点 Cron，最多 90 分钟、maxSourceCalls=1。
2. authority：为 L 依次生成 source selection、runtime control、schedule control binding；每阶段独立 key/Receipt，旧 binding 仅作不可变 predecessor，不复用旧安装权限。
3. policy：以 revision 7 为 prior，生成同一 Case 的 revision 8 并单独审批、put；policy 在 Cron 观察窗内有效。
4. event-control：独立审批 expand，将第十条 event-control 加入 L group 36→37；随后独立审批 enable，生成 L policy binding revision 1。
5. natural observe：只 PATCH schedule enabled，不调用 POST run；由 API Cron worker 在整点以 trigger=cron 幂等领取，最多读取一次真实 source。观察 schedule run、ingress journal、occurrence、dispatch attempt、Case/Run；成功或超时后立即把 schedule disabled。
6. close：无论链路是否生成新经营任务，都以真实数据和 Receipt 判定；不得为了“做绿”补造 Case。未知写结果只读回，不换 key 重发。

## 停止与恢复规则

- L 身份、配置、cutover Resume、九路 group 36、source 配置或真实商城连通性任一漂移，在 authority 前停止。
- 任一阶段已有 intent 且结果未知，只按固定 key/Receipt 读回；不得删除 intent 或重新审批掩盖结果。
- event-control expand 前 policy revision 8 必须可读回；enable 前十路必须同为 L/group 37。
- Cron 运行失败、超时或模型处理较慢时，保留 durable run/occurrence 状态，先关闭 schedule，再按同一 occurrence 恢复；禁止再触发第二个 source run。
- external effects、内容发布、消息发送、230 L0 始终不在本波授权范围。

## 文件范围

- `scripts/a0v_p02_current_preflight.py`：仅增加默认 15 分钟不变的可配置授权窗口。
- `scripts/a0v_l_product_preflight.py`
- `scripts/a0v_l_product_window.py`
- `scripts/a0v_l_natural_api.py`：在既有独立 snapshot worker 启动配置上仅开启真实 Cron worker，继续禁止 API 进程内 Host。
- `scripts/a0v_l_natural_product_event.py`
- 对应失败关闭测试与本波证据。

复用现有 Pipeline Control Owner、schedule policy、event-control lifecycle、canonical router 和 Cron worker，不改领域写模型。
