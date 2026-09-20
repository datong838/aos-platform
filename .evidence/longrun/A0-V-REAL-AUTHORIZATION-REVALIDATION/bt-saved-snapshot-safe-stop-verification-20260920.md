# BT 保存快照恢复安全停止验证（2026-09-20）

## 结论

`BT_SAVED_SNAPSHOT_NOT_STARTED_HOST_STOP_BOUNDARY_FROZEN`。

本波没有转移definition、没有renew、没有enable、没有创建attempt，也没有读取商城源数据。唯一外置
Runtime Host在进入纯HTTP前被正常停止；Host stop协议把BT从rev6/epoch3 enabled/ready推进为
rev7/epoch4 disabled/fenced/desired enabled/observed unknown，并确认3/3 runtime resources released。
该generation不得原地复活，故按fail-closed终止本波并转入正式退休与direct successor。

## 1/6 plan 与前置基线

- HEAD `3e1d38bf`；BT installation/generation为
  `b05b7f06-67a0-4ea1-bc7c-1ba2108653d5` /
  `2c2d4cd5-d9bd-45b4-86d9-72a979eb0a58`，原binding rev6/epoch3 enabled/ready，
  九路rev183/group210，attempt=0。
- definition rev127 disabled/hash
  `sha256:4e373626f25a3fcb643e04f5cf3468b553c5c03815c347098840a18c15697aa0`；recovery
  rev41/hash `sha256:400cf5d221f28501d763b194fb412a18a2c23c872057fe6e5f4c896a7721935d`。

## 2/6 Host停止与纯HTTP证据

- 唯一Host PID 4492正常输出 `RUNTIME_HOST_STOPPED`；读回Host=0、snapshot worker=0、18181=0。
- 受控纯HTTP preflight为 `CONTROLLED_API_LOCAL_DIAGNOSTIC_PREFLIGHT_GREEN`，明确
  Cron=false、snapshot worker=false、进程内Host=false、sourceCalls=0、runsCreated=0；
  `/openapi.json` HTTP 200。
- 纯HTTP期间首次 `prepare` 在只读binding门失败，未形成immutable result、未写definition/recovery。
  原因不是未知提交，而是Host stop已正式推进binding边界。

## 3/6 边界复核与禁止原地复活

- 曾以唯一外置Host PID 9765复核自然重启能力；Host启动成功但 `liveTargets=[]`，binding仍保持
  rev7/epoch4 disabled/fenced。没有第二Host、没有operation重发、没有attempt。
- 因正式Host stop后的generation不可恢复为旧rev6/epoch3，未放宽preview、未手工修改binding、
  未执行transfer/renew/enable。纯HTTP与空载Host均正常停止。

## 4/6 最终权威

- BT binding rev7/epoch4，enabled=false、operation_fence=true、desired=enabled、observed=unknown；
  resources 3/3 released；attempt=0。
- definition仍rev127 disabled，recovery仍rev41；九路仍为BT rev183/group210。
- 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link=0`、
  projection pending=0、canary=0。
- 最终Runtime Host=0、snapshot worker=0、18181=0；无未知外部结果。

## 5/6 验证

- 本波未保留未经执行验证的BT saved-recovery实现；仅保留plan与本verification。
- `git diff --check` 与现有BT定向测试在提交前复核。

## 6/6 下一波

自动进入 **BT 正式退休与 BU direct successor**：以rev7/epoch4 fenced、3/3 released、attempt=0、
definition rev127 disabled、recovery41、九路rev183/group210为exact authority；正式disable settlement
目标binding rev9/epoch5与legacy rev185/group212，取得detach Receipt后创建BU并恢复唯一Host。
