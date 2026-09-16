# Y4 整组周期执行与恢复接线施工方案

2026-09-16。前置：Y3c-5完整失败Store恢复验收通过后实施；本文件登记方案，不宣称worker已启动或真实首链已完成。

## Y4a实施证据

新增只读Dispatch和对应PG测试。Red为新增模块尚不存在的收集失败（`/tmp/aos-dispatch-red.log`），实现后专项5 passed/23.55s（`/tmp/aos-dispatch-final.log`）；原defined claim及recovery-only禁入回归11 passed/25.46s（`/tmp/aos-dispatch-regression.log`）。diff检查通过。

组身份只含租户/定义标识/UTC分钟；未完成原组包括全停止失败均阻止后续slot，配置revision变化保留本slot已完成组身份；新周期候选、停用、负租户、续期专用配置均覆盖。routing完成状态使用具名SQL夹具，只证明状态分流，不声称实际Store完成或当前执行许可。实际Store证据由C5提供。输出始终executionAuthorized=false；Y4b必须在会话锁内重读并经原Runtime检查。未接应用启动、未发源调用、未迁移主库。

## Y4b实施证据

新增同步Worker，稳定定义会话锁覆盖锁内重查及原Runtime执行，Factory复用原SourceClaim/Control/Store与runtime_worker_connection。Red为Worker模块缺失；专项3项通过，工厂+Worker+Dispatch联合14 passed/35.54s（`/tmp/aos-worker-final.log`），diff检查通过。第二连接执行实例在原执行回调期间返回busy；原Claim提交后具名确认异常保留原组，第二实例读取pending而不再execute；停止/停用零源；tick异常用固定unknown编码不泄漏异常内容，也不写虚假stopped。工厂构造无连接，两个原Runtime共用授权与Store。

本波执行回调使用明确停止seam，只证明锁、原Claim和调度错误边界，不替代C5实际Store链验收。main未注册Worker。下一波Y4c先实现async serve与线程真实排空测试，再接默认关闭的main入口和状态；恢复执行正式入口仍待Y4d。

## Y4c1线程排空证据

初次测试因遗漏隔离DSN而在默认5433拒绝连接，未计为逻辑Red；补齐18434测试配置后，以修改前Worker验证缺少serve（1 failed/4.34s，`/tmp/aos-worker-drain-red-confirmed.log`）。实现后生命周期/Factory/Worker联合13 passed/17.00s（`/tmp/aos-worker-drain-final.log`），diff检查通过。

真实Python线程具名tick seam分别验证Task.cancel（含第二次取消）、async停止事件、host失活；线程收到threading.Event后延迟清理时，serve保持STOPPING且Task不结束，释放清理门后线程退出才STOPPED。预停止、host未就绪不启动tick，重复serve拒绝。未访问业务源/Store、未改数据库Run终态。下一波c2把默认关闭的应用入口接到已验证serve，并确保Store资源在serve实际排空之后释放。

## Y4c2应用接线证据

main默认关闭的新入口已接线；显式启用必须有活host与工厂。启动构造异常FAILED_CLOSED，生命周期开始清空旧worker状态。serve持有lazy Store上下文直到真实线程排空；原shutdown设置stop并等待task，之后才清理连接资源。Red缺少启动helper（1 failed/3.71s）；初次Green测试夹具因yield后清理未放finally而失败，改为与生产_authoritative_store一致的finally后，通过联合23项/3.98s（`/tmp/aos-snapshot-main-verified.log`）。覆盖原runtime startup composition、stop/host/cancel真实线程及构造失败资源释放。diff检查通过。

测试未启动真实源，不表示主服务已加载；主环境未设置启用开关、未重启/迁移。下一步Y4d先提供受当前principal保护的服务端状态与原续期回执自动消费设计，再接页面；禁止另起不受上述生命周期管理的执行线程。

## Y4d1正式续期自动承接证据

原worker在同定义锁内读最新RecoveryReceipt，exact currentDefinitionRef匹配才交原RecoveryRuntime，执行者来自持久回执。Red为原先只返回pending（1 failed/12.73s）；恢复接线、普通worker与线程生命周期联合9 passed/34.42s（`/tmp/aos-worker-recovery-green.log`）；新增实际撤销持久membership后经原RecoveryRuntime在Store前拒绝，1 passed/12.41s（`/tmp/aos-worker-recovery-permission.log`）。diff检查通过。

锁内第二实例busy、具名完成路由后不重复承接、停用拒绝、无审批原组仍pending。完成路由是明确seam，不替代C5实际Store；撤权负例走真实原Authority，源仍原准备一次、零Store写入。本波无新队列/执行POST，065审批回执即持久恢复依据，所有副作用仍限原Owner链。后续Y4d2当前principal保护状态API、Y4d3配置/恢复页面与浏览器验证；主环境仍未启用/迁移/重启，真实首链未完成。

## Y4d2授权运行状态证据

新增GET定义/runtime，Service先当前管理权限、原Dispatch只读状态/恢复引用、末尾重验权限与exact定义；所有输出executionAuthorized=false，零源零Run创建。进程状态只显示同租户、存活host和后台任务，active仅匹配当前定义；Worker在真实Runtime入口设置active_definition_id、finally清除。追加原worker PG测试断言该范围与清除。

Red缺read_runtime_status（1 failed/8.24s）；PG当前权限/原组只读+HTTP首轮28 passed/14.30s，补live host/task/其他定义/撤权显示后HTTP+Worker/线程回归34 passed/18.61s（`/tmp/aos-runtime-status-green.log`、`/tmp/aos-runtime-status-final.log`）。diff检查通过。HTTP服务与进程夹具只验证契约，PG当前membership撤销确实拒绝，不能把状态响应当作业务完成。

下一波d3在既有SnapshotSchedulesPanel/API契约中展示真实状态、处理定义漂移/租户切换，再补正式续期交互与浏览器验收。应用主环境仍未加载/启用。

## Y4d3a状态页面证据

既有API客户端新增严格runtime解析；租户/配置exactRef、执行授权false、状态布尔逻辑、aware时间与原恢复ref不匹配一律拒绝。面板选中配置后只读加载状态，可手动刷新；请求序号、卸载和租户身份检查丢弃旧响应。配置enabled但worker disabled明确显示执行器尚未启用，不再使用“执行调度尚未接通”固定文案。

Red新增readGroupRuntime未实现；API/组件16项通过，类型检查与Vite构建通过（既有chunk大小提醒保留）。独立Chrome/15174预览全部API拦截，fixture显式标注“隔离验收实例（非真实商城）”；未启用、执行中、原组待恢复、已批准待承接、配置exactRef漂移、760宽度均通过，真实请求/源读/fixture写均0，pageerror=0。脚本、结果与四张截图位于y4d3a-status-ui；桌面/760均目视检查，新面板无横向溢出，原窄屏侧栏仍占上方空间。时间与按钮间距复用原header布局后重新构建/浏览器验证。日志/tmp/aos-status-ui-browser-final.log。

这里只证明客户端及隔离浏览器状态显示；真实后端运行状态API已由d2 PG/HTTP验证，主服务尚未加载，未声称真实浏览器经营闭环。下一波d3b原任务上下文/正式续期窗口/原key确认交互，不自动重发未知写；然后Y5/Y6/Z。

## 产品与技术目标

让已安装、当前获准的十二路配置自然产生同一快照组；失败或未知结果保留原组事实，通过正式续期回执恢复，不依靠开发者逐路调用。执行身份来自服务端持久化定义，配置者与执行者的当前权限继续由原Owner检查。保持原单路未接管路径和所有租户、预算、审批、安装代次围栏。

## 分波施工与文件范围

Y4d3a先显示状态，文件：`apps/web/src/api/snapshotSchedules.ts`及`.test.ts`、`apps/web/src/pages/s2/SnapshotSchedulesPanel.tsx`及`.test.tsx`。新增严格解析runtime响应（租户/definition/exactRef/状态/布尔值/时间/恢复ref），复用原请求身份快照。选中已保存配置后读取真实状态并提供只读刷新；不轮询写入、不自动审批。组件请求序号与卸载/租户保护阻止旧结果覆盖新选择；配置版本漂移明确要求刷新配置。删除过期“尚未接通”固定说法，换成“选中配置查看当前运行情况”及服务端分态：未启用执行器、停用、运行中、待原组恢复、已批准等待承接、等待周期、需重新配置、结果未知。无worker可用时不能显示已在运行。正式续期表单另列d3b实现；本波不以状态页替代恢复交互完成。运行前端测试/类型构建，隔离浏览器用具名API响应验证布局与状态；真实后端浏览器联调留Y6加载后的验收。

Y4d2状态API文件：修改 `pipeline_snapshot_schedule_service.py`、`routers/pipeline_snapshot_schedules.py`、`pipeline_snapshot_schedule_worker.py`，新增 `services/aos-api/tests/extension_runtime/test_snapshot_runtime_status_pg.py` 并扩展 `services/aos-api/tests/test_pipeline_snapshot_schedule_http.py`。GET /v1/pipelines/snapshot-schedules/{definition_id}/runtime 使用principal scope/subject，先当前管理权限，再原Dispatch只读状态及原RecoveryReceipt引用，末尾复验当前权限和exact定义；输出始终executionAuthorized=false，无业务原始行/连接资料。进程投影只在worker.scope与principal相等且worker Task/host存活时显示可用，明确disabled/stopped/failed与activeDefinitionId；不展示其他租户或定义的执行信息。该进程观察不是集群全局执行证明，也不是执行授权。worker在锁内进入实际Runtime前设置active_definition_id，finally清除。页面下一波对exact定义漂移和租户切换丢弃旧状态。

Y4c2追加精确接口：main新增 `_start_snapshot_group_worker(app)` 和显式 `AOS_SNAPSHOT_GROUP_WORKER_ENABLED`（默认false）。只有已运行host及原factory存在才可启用；缺失依赖启动失败，不宣传可调度。应用持有worker/task/状态，注册stop事件和后台task，复用原shutdown drain。任务上下文持有_authoritative_store（lazy engine），serve完全退出后才dispose；实际数据库连接仅由worker线程创建。新增 `services/aos-api/tests/test_snapshot_schedule_main_lifecycle.py`，验证默认关闭无工厂调用、明确启用缺host拒绝、原shutdown等待实际线程退出后再释放Store。原runtime startup composition回归。主运行环境不开启新开关。

Y4b追加测试目录：`services/aos-api/tests/test_pipeline_control_service.py`，验证原Factory构造无连接/无源调用且两个Runtime共享ControlOwner/Store/runtime身份；现有工厂测试一并回归。

1. Y4a：固定周期计划和原组状态读取。新增 `services/aos-api/aos_api/pipeline_snapshot_schedule_dispatch.py` 与 `services/aos-api/tests/extension_runtime/test_snapshot_schedule_dispatch_pg.py`。复用DefinitionOwner解码、原ScheduleClaim及成员Run事实、原Cron解析。配置定义标识、租户、UTC分钟构成稳定组身份；不以可变revision生成另一个同分钟组。新的领取仍交原ScheduleClaimOwner执行CAS和完整当前控制验证。
2. Y4b：工厂及受管理执行。修改 `services/aos-api/aos_api/pipeline_control_service.py`，新增 `services/aos-api/aos_api/pipeline_snapshot_schedule_worker.py` 与对应worker测试。只构造原ScheduleRuntime、RecoveryRuntime、Store和runtime_worker_connection。每定义会话锁覆盖执行全过程；同一锁内重新读取当前状态，再决定新领取、原组继续、等待明确恢复或拒绝。不可在锁外扫描结果上直接执行。
3. Y4c：应用启动、关闭与状态。修改 `services/aos-api/aos_api/main.py` 及相关lifespan测试。默认不开启主库新worker；选项显式启用，依赖runtime host健康。线程安全cancel_event贯穿原Runtime，停止新任务后等待同步执行真实退出，之后才清理共享连接/隧道。超时或结果不明保留unknown，不能虚写executor_stopped。状态接口返回实际进程与数据库事实。
4. Y4d：正式恢复执行请求与界面。复用 `services/aos-api/aos_api/routers/pipeline_snapshot_recoveries.py`、`pipeline_snapshot_schedule_service.py` 及现有配置页面；具体前端文件由页面定位后补全清单。请求只指定exact回执与原幂等键，principal当前授权通过后交同一个受管理worker。不得另起无生命周期管理的后台线程。页面显示停用、可调度、执行中、等待恢复、unknown、需重配；只有实际启用才替换“尚未接通执行”。

## 原组优先与未知结果边界

Y4d1方案细化与替代：恢复已拥有065正式审批回执，复核后不新增另一套HTTP执行队列/幂等账本。修改 `pipeline_snapshot_schedule_worker.py`，新增 `services/aos-api/tests/extension_runtime/test_snapshot_worker_recovery_pg.py`。当前enabled定义只有一个待处理原组时，在同定义session锁内读取原最新RecoveryReceipt；仅当其currentDefinitionRef等于当前候选exact定义，才交原RecoveryRuntime.resume_saved，actor取回执executor，当前权限、控制窗口、原输入/Run仍由固定Authority全验。无回执或多个待处理组只返回pending；过期/撤权/旧回执不会授权。完成后原Run事实使后续tick不再消费；同Receipt未知结果按原Runtime幂等恢复，无新源或新Run。原renew HTTP仍只提交审批，本身不启动线程；启用受管理worker后自然承接已审批原组。这替代上文Y4d新增独立执行POST的初步设想，减少平行执行通道，保留持久原回执与服务端固定身份。

Y4c拆为c1线程排空、c2应用接线。c1修改 `pipeline_snapshot_schedule_worker.py`，新增 `services/aos-api/tests/test_snapshot_schedule_worker_lifecycle.py`。serve只允许单实例一个循环，async stop/host失活/Task.cancel均传播至threading.Event；active to_thread任务用shield保护，取消协程后仍等待实际任务完成，期间状态STOPPING、禁止再tick。只有底层任务退出才STOPPED，不改数据库Run终态。重复取消同样不能丢弃底层任务；线程抛错只保存固定错误码，不能把错误文本暴露状态。纯线程夹具验证取消过程中延迟清理、host失活、预停止零执行、重复serve拒绝；c1通过后才进入c2 main默认关闭入口与启动/关闭集成。

Y4b接口细化：`PipelineSnapshotScheduleWorker(scope,runtime,recovery)`只接受原两个Runtime且共享ControlOwner，`run_definition(definition_id,cancel_event,deadline)`先检查停止，获取按scope/definition稳定的非阻塞PG会话锁，再用数据库当前时间只读inspect；只有due走原Runtime.execute，actor/definitionRef/groupId/slot均取服务端结果，其他状态只返回。锁贯穿源读取及Store完成，finally释放；原异常向上传递，不写假的停止/完成状态。`tick`从当前租户定义头枚举enabled，串行调用，逐项异常记录固定unknown状态、原定义标识且不包含敏感异常文本。持锁失败返回busy，不排队后自动重读源。Factory新增build_snapshot_worker(scope,store)，复用原依赖及get_engine；本波不注册main启动，async serve停止协议留Y4c。测试用具名Runtime执行seam验证锁覆盖、原claim提交后异常与再次tick阻断，明确不替代C5实际Store验收。

- 本分钟已有原ScheduleClaim时保留其exact定义/成员身份；同分钟改配置不能创建第二组绕过原回执。
- 跨分钟存在原组running、failed或未知时，不仅检查active Run谓词，还检查完整十二成员和原组完成事实。全失败且stopped也不能直接跳过原组开新周期。
- 原SourceClaim存在而Input未落盘是未知读源结果，禁止重读。Input已保存时只按现有执行窗口或正式RecoveryRef恢复；续期专用定义继续被066围栏禁止新读源。
- 已完成组可进入下一合法周期；当前源权限、控制窗口过期、配置禁用或安装代次不匹配时仍拒绝。不得为周期运行自动放宽24小时窗口。
- worker重启或重复tick不更换原组/幂等键。数据库提交确认未知时先读取原回执，不能重领新的组。

## 验证与退出条件

Y4a接口细化：`snapshot_slot_group_id(scope, definition_id, scheduled_for)`仅接受exact租户、canonical UUID和aware整分钟，规范UTC后UUIDv5，不含revision。`PipelineSnapshotScheduleDispatch(definitions, claims).inspect(conn, scope, definition_id, now)`只读且返回executionAuthorized=false；读取完整原Claim及十二Run状态，只要存在未完成历史组，返回original_group_pending及原组路由，绝不返回新领取。全完成同slot返回slot_completed。没有待处理组、当前非续期专用且cron命中才返回due候选；这不是执行授权，Y4b必须在持锁后再次inspect并调用原Runtime。disabled/retired/recovery_only/not_due分别返回明确状态，不读源、不新建Run、不替用户续期。

先Red/Green验证固定分钟身份、配置revision变更、跨分钟未知阻断、普通已完成组下一周期、续期定义不新读源；随后双连接并发同slot、锁竞争、当前权限撤销、disable竞态、停止信号传播和底层线程实际退出。保留旧单路回归、租户负例、卸载禁入及重装代次负例。工厂测试验证原Owner依赖，浏览器验证真实服务状态而非硬编码。

测试均隔离，涉及PG的套件串行。Y4完成后接Y5十二路真实配置、Y6克隆库迁移演练与受控主服务切换，之后Z原业务Run处置及真实经营闭环。任何isolated Green都不计为真实源业务验收。回滚为关闭新增worker入口并保留不可变证据；不删除原Run/Receipt、不回滚用户数据。
