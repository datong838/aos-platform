# W5c3n Predecessor-free 路由权威只读清点方案（2026-09-24）

## 起点与目标

W5c3m `7f761b9c`：第三个干净安装 active/etag5、binding rev4/epoch3 enabled/ready/fence off，Host PID17302 同 Job/三 held 资源；九路仍 legacy/fenced、12 调度 off、attempt/canary0。安装 composition 的 predecessor 为 null，旧 DS/两次失败安装均已卸载。历史 `a0v_w5_ds_successor_business.py` 的注册请求强制旧 predecessor active 与精确 detach Receipt，不能直接移植。

本波仅识别九路当前 group/revision、历史注册/切换/分离 Receipt、原 `FirstDispatchRegistrationService.register` 与 `register_successor` 在当前历史 group 上的限制，以及 12 条 selection/control/definition 的实际 head/有效期。产出下一波精确写入路径或清楚的代码缺口；不注册、不 prepare cutover、不开放调度、不读商城源、不运行业务。

## 串行步骤

1. 确认 m1/工作树、W5c3m 正式 Receipt/Host/lease、九路 9/9 legacy/fenced、12 调度 off、运行中 attempt/unknown dispatch/canary0，四来源及预算当前。若已漂移，只记录阻断。
2. 仅查询元数据：九路 group/revision 与历史注册、cutover、detach Receipt 的身份/终态/哈希（不读取商城源 payload）；当前新安装有无注册 Receipt/activation；12 个 selection/control/definition 的 ID、revision、有效期、enabled 状态。
3. 对照产品/技术方案和原 Owner 的 Python/SQL 函数门禁，验证 predecessor-free 新安装应走 first registration、successor registration，还是需要最小新 Owner 路径。不得以 dry-run 或旧脚本代替正式权威。
4. 写 verification，明确下一波每一步和停止条件；m1 commit。仅在后续独立方案批准后才提交注册或切换请求。

## 停止条件

任何 Host/Job/lease/预算/九路/调度/attempt/canary 漂移、旧操作未终态、无法区分历史与现行 Receipt、权限不明或数据查询可能读取商城源，则停止写入并只读对账。未知结果不重发，不能手工 run_definition。
