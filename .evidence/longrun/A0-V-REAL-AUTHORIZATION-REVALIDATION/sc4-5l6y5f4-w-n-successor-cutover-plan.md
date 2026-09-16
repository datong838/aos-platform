# SC4-5L6Y5F4 W：N successor 登记与九路原子切换方案

日期：2026-09-17

## 权威输入

- N installation `d42cd39a-bc44-403b-a184-c241cae7769e`，revision 5，lock `sha256:15ac55d0ca7098c4df286ad70b6a20e79c327b0ec9c53baceea7cbb7059fcae8`。
- generation `677046ff-6147-4b3b-905d-9e12964b6581`，binding revision 4 / epoch 3 / enabled / unfenced / ready。
- configRef `2006f9db-e89b-4ea6-82e6-adbec0c5e8ed@1`，hash `sha256:9ad6dc8af8c7b15d7b04b4635b9d02a3f4146b1be45ec244bb6461fb2a52ee0f`。
- L 最终 detach Receipt `e43b1b5c-77b7-4fc2-bb35-3cb29a9a54c2`，hash `sha256:c87738ebc3a779961d8752273e83cb9d45e8f47f797b46a5c18f1285724ed2fa`。
- 九路当前全部为 legacy/fenced，route revision 23，group `6a402d31-83ad-546c-807f-508c87498ce1` revision 41；running/claimed/unknown=0，canary=0。
- Runtime Host PID 10115 为 active，唯一 live target 是 N；商品 Policy9 已 disabled，本波不恢复 schedule。

## 固定阶段

1. preview：精确校验 N head/binding/config、三份 live resource、四个 succeeded operation、L 正式 uninstalled、L detach Receipt/hash、九路 group41 快照、零 inflight 与 canary。
2. register：复用正式 `SuccessorDispatchRegistrationService`，expectedGroupRevision=41；保留不可变 intent/result。intent 已存在时只读同 installation/key/actor Receipt，不以新 key 重发。
3. approve：登记 Receipt 现场读回一致后，建立 externalEffectsAllowed=false、fallbackAllowed=false 的独立 cutover policy；操作 ID 固定为 `66bd45d9-1a5d-5041-b90f-462bea7d807a`。
4. prepare → pause → commit → validate → resume：逐阶段固定 intent/result，严格引用上一阶段 Receipt；未知结果只读 activation history，禁止跨阶段重发。
5. readback：九路全部为 N extension/unfenced，group revision 单调到 42，route revision 单调到 24；N runtime revision 单调到 6，Host 唯一目标仍为 N；Policy9 和所有 schedule 继续 disabled，零业务 Run、零外部副作用。

## 文件

- `scripts/a0v_n_successor_business.py`
- `scripts/a0v_n_successor_cutover.py`
- `scripts/a0v_n_successor_cutover_verify.py`
- `services/aos-api/tests/extension_runtime/test_a0v_n_successor_business.py`
- 本目录 W 阶段执行与最终证据。

## 停止条件

任一 N/L 身份、revision、资源、operation、detach Receipt、路由、Host target、inflight 或 canary 漂移即停止。registration Receipt 未确定不得 approve；每阶段 intent 存在但结果未知时不得重发。整个 W 波不启用商城来源、事件策略，不造 Case/Run，不执行外部发布。
