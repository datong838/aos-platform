# W5CB4 E17-o｜API 内嵌 Host 与独立 Host 准入拓扑审计

## 实际控制流

1. `routers/bundle_runtime_installations.py:create_bundle_runtime_operation` 在 runtime-apply/verify 时调用 `RuntimeLifecycleService.request_preparation`；它传入的 `current_preparation_executable` 只看**同一 API 进程**的 `extension_runtime_host_status='ACTIVE'`、未结束的 task、selection.host 的当前精确租户 assignment。没有进程内 Host 时，操作在持久化前拒绝。因此“先有 runtime-apply 操作再启动 Host”在当前 API 路径上循环依赖。
2. `main.py` 启动时直接 `build_production_runtime_host_selection`，ACTIVE 就在 API 进程创建 `host.serve()` task，随后启动自然业务 worker。`control_wiring.py` 仅凭 `AOS_EXTENSION_RUNTIME_HOST_ENABLED=1`、三身份凭据引用（或两条 DSN）、OCI context、platform 构造依赖；它不会调用 E17-l 当前签名/物理库交叉预检，也不要求当前安装目标。三身份若一起指向旧库，生产选择器的“彼此同库”仍不足以证明与当前签名安装同库。
3. E17-m 加固的是 `scripts/a0v_ecommerce_runtime_host.py` 的**独立进程命令入口**；该进程的 selection/task 不会填入 8080 API 进程的 `app.state`。所以即便未来独立 Host 运行，当前 HTTP runtime-apply 路由仍不会因它而自动接受请求。独立 Host 禁入不等于 API 内嵌 Host 禁入。
4. 当前运行的 8080 由 `a0v_current_preview_http.py` 显式设置 `AOS_EXTENSION_RUNTIME_HOST_ENABLED=0`、所有自然 worker 关闭；当前库 operation/binding/assignment 为 0，18181 未监听。该现场安全禁入不证明未来人为设置 Host flag 时 API 路径已安全。

## 下一波最小修复边界

E17-p 在**API 内嵌 Host 选择前**加入当前签名 Receipt 与受保护三身份物理库交叉门；缺 Receipt、旧目标库、权限/assignment 缺失或未知结果直接 INACTIVE，且不构造 worker。必须明确当前 preview API 关闭状态不变；不得因签名预检 GREEN 就自动许可未获审批的业务操作。之后另波处理正式配置/审批/预算及有界启用。先文件级方案、RED、最小实现，专测同时覆盖 `main.py` API 路径和独立脚本不互相冒充。

本波为只读代码审计，无当前库写入、Host/worker/Provider 启动、旧 12 Run 回放或商城源读取。`browser-pilot` 截图仍待补。
