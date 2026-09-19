# AP 失败退休与 Runtime Host 重载验证

## 正式退休结果

- preflight：`AP_FAILED_RETIREMENT_PREFLIGHT_GREEN`。
- disable operation：`feefe9f4-0dba-442f-a87a-e6b90509c583`，expected binding revision 6。
- delivery：由 Runtime Host 自然领取，`claimedByHost=true`，`resendDisable=false`。
- lifecycle：1 个 operation、2 个 Receipt，顺序为 `fence → detach`。
- AP binding：rev8、executionEpoch4、enabled=false、operationFence=true、desired disabled、observed unknown。
- 路由：九条全部回 legacy，revision101、cutover group revision128。
- 资源：3/3 released；running attempt=0、unresolved=0、runtime pending=0、canary=0。
- snapshot：definition rev63 disabled；12 个 Run、12 个 Dataset Receipt 保留；Store Receipt、live link、projection pending 均为 0。

## Runtime Host 重载

- 旧 Host：PID 59258，启动于 2026-09-19 09:22:00+08:00。
- 严格 Store 修复：commit `b287ccbb`，提交于 2026-09-19 13:44:56+08:00。
- 新 Host：PID 87894，启动于 2026-09-19 14:07:14+08:00，LaunchAgent state=running。
- `ecom_consistency_store.py` SHA-256：
  `aee6b5cebac9c7bc7b9a8e9582e8185cfc896cd1af20a589a475ceda27f2883c`。
- 新 Host 启动日志：`RUNTIME_HOST_ACTIVE`，tenantCount=1，positiveTenant=`org-org/dev-project`，
  canaryTenantCount=0。

新进程启动时间晚于修复提交，因此后续 successor 的 Store 执行将加载修复后的批量 strict-link locking 实现。

## 验证与边界

- AP/前代退休专项测试通过；退休 audit 在 Host 重载后再次保持 green。
- 浏览器 8434 `/ontology` 仍正常渲染 AOS v1.6.5 与缓存本体导航；因 qcursor 仍按方案停机，页面显示离线、
  写队列 0，符合当前控制面状态。
- 本波没有创建 successor、没有调用 snapshot definition、没有源重读、没有 Store 重发、没有外部副作用。

## 下一波

基于 AP detach Receipt 与 legacy group128，准备 AQ direct successor：新 installation/generation、签名配置、
replacement、成功注册、九路由 cutover、saved snapshot transfer/renew/enable。全程先预览后单写，仍不启动 qcursor，
直到 AQ authority 与新 Host 基线全部复核通过。
