# AQ 失败退休与 Runtime Host 重载验证

## 正式退休结果

- preflight：`AQ_FAILED_RETIREMENT_PREFLIGHT_GREEN`。
- disable operation：`e45d1c14-ebe0-43e0-bd24-75feb26a9a69`，expected binding revision 6。
- delivery：由 Runtime Host 自然领取，`claimedByHost=true`、`resendDisable=false`，没有重发未知结果。
- lifecycle：1 个 operation、2 个 Receipt，顺序为 `fence → detach`。
- AQ binding：rev8、executionEpoch4、enabled=false、operationFence=true、desired disabled、observed unknown。
- 路由：九条全部回 legacy，revision104、cutover group revision131。
- 资源：3/3 released；running attempt=0、unresolved=0、runtime pending=0、canary=0。
- snapshot：definition rev66 disabled；唯一 AQ attempt
  `16ca3c76-4dbe-48c3-9ff3-4f06eb9fbc82` 仍为 rev11 failed，terminal 为
  `RECOVERABLE_INGRESS_DEADLINE_EXCEEDED / IngressJournalConflict`；12 个 Run 与 12 个 Dataset Receipt 保留；
  Store Receipt、live link、projection pending 均为 0。

## Runtime Host 重载

- 旧 Host：PID 87894，启动早于 strict-link 远端写入批量修复。
- 修复 commit：`2ce96305`，提交于 2026-09-19 15:01:54+08:00。
- 新 Host：PID 93413，启动于 2026-09-19 15:06:38+08:00，LaunchAgent state=running、runs=7。
- `ecom_consistency_store.py` SHA-256：
  `f146d87091922b89c1a3a589d2f519e464e6677c6d9f04ffa9faa2595396ab8d`。
- 新 Host 最新启动日志为 `RUNTIME_HOST_ACTIVE`，tenantCount=1，positiveTenant=`org-org/dev-project`，
  canaryTenantCount=0；该 active 标记之后 `HOST_RUNTIME_FAILED` 计数为 0。
- qcursor LaunchAgent 不存在，防休眠进程保持运行；AR authority 完成前不恢复 qcursor。

新进程启动时间晚于修复提交，后续 successor 的 Store 执行将加载批量 strict link insert/update、批量 projection
revision 读取和批量 outbox insert 实现。

## 验证与边界

- AQ 退休 audit 在 Host 重载后返回 `AQ_FAILED_RETIREMENT_GREEN`。
- 退休、saved recovery 与 attempt guard 专项测试串行执行；浏览器 8434 `/ontology` 复验只读取缓存与控制面状态。
- 本波没有创建 successor、没有调用 snapshot definition、没有重读源数据、没有 Store 重发，也没有外部副作用。

## 下一波

基于 AQ detach Receipt 与 legacy group131，准备 AR direct successor：新 installation/generation、签名配置、
replacement、成功注册、九路由 cutover、saved snapshot transfer/renew/enable。全程先预览后单写；在 AR authority、
新 Host 基线和防重边界全部通过前，不启动 qcursor。
