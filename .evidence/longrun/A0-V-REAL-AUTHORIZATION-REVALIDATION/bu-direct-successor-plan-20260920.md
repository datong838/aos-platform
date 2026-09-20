# BT 正式退休与 BU direct successor 方案（2026-09-20）

## 1. 当前权威

- HEAD `f5ce9d56`；BT installation `b05b7f06-67a0-4ea1-bc7c-1ba2108653d5` / generation
  `2c2d4cd5-d9bd-45b4-86d9-72a979eb0a58`，binding rev7/epoch4 disabled/fenced/desired enabled/
  observed unknown，Runtime Host=0，attempt=0，3/3 resources released。
- definition rev127 disabled；九路仍指向BT extension rev183/group210。
- 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link=0`、
  projection pending=0、canary=0。

## 2. 串行步骤 1-6

1. **plan/preflight**：固定BT released/binding/routes/definition/零副作用与Host=0边界。
2. **BT正式退休**：通过原disable Owner唯一提交，目标binding rev9/epoch5 disabled/fenced/desired
   disabled，九路legacy rev185/group212，并取得唯一detach Receipt；未知结果先对账不重发。
3. **BU创建与lifecycle**：仅以BT detach Receipt为predecessor，串行create、prepare、verify、stage、
   configure、enable；prepare accepted后只启动唯一外置Host自然领取。
4. **注册与九路cutover**：唯一注册幂等键，串行approve、prepare、pause、commit、validate、resume，
   目标九路rev186/group213。
5. **唯一Host与健康观察**：第二Host=0、18181=0、snapshot worker=0；只读观察lease renewal、
   binding ready、routes与attempt=0。
6. **verification/commit**：读回12/12与全部零副作用，落verification、测试、精确提交；下一波
   在Host保持唯一在线的前提下执行BU saved-snapshot recovery。

## 3. 停止条件

BT资源非released、disable/Receipt/CAS漂移、出现第二Host/worker/attempt、商城源读取、负租户写、
业务副作用或未知提交边界时立即fail closed；不得原地复活BT或重发未知请求。不push、不动其他分支，
230 L0继续挂起；非人工决策工程问题由当前唯一开发最小修复并继续。
