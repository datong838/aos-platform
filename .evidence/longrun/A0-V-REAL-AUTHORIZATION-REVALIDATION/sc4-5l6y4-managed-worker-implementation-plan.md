# Y4 整组周期执行与恢复接线施工方案

2026-09-16。前置：Y3c-5完整失败Store恢复验收通过后实施；本文件登记方案，不宣称worker已启动或真实首链已完成。

## 产品与技术目标

让已安装、当前获准的十二路配置自然产生同一快照组；失败或未知结果保留原组事实，通过正式续期回执恢复，不依靠开发者逐路调用。执行身份来自服务端持久化定义，配置者与执行者的当前权限继续由原Owner检查。保持原单路未接管路径和所有租户、预算、审批、安装代次围栏。

## 分波施工与文件范围

1. Y4a：固定周期计划和原组状态读取。新增 `services/aos-api/aos_api/pipeline_snapshot_schedule_dispatch.py` 与 `services/aos-api/tests/extension_runtime/test_snapshot_schedule_dispatch_pg.py`。复用DefinitionOwner解码、原ScheduleClaim及成员Run事实、原Cron解析。配置定义标识、租户、UTC分钟构成稳定组身份；不以可变revision生成另一个同分钟组。新的领取仍交原ScheduleClaimOwner执行CAS和完整当前控制验证。
2. Y4b：工厂及受管理执行。修改 `services/aos-api/aos_api/pipeline_control_service.py`，新增 `services/aos-api/aos_api/pipeline_snapshot_schedule_worker.py` 与对应worker测试。只构造原ScheduleRuntime、RecoveryRuntime、Store和runtime_worker_connection。每定义会话锁覆盖执行全过程；同一锁内重新读取当前状态，再决定新领取、原组继续、等待明确恢复或拒绝。不可在锁外扫描结果上直接执行。
3. Y4c：应用启动、关闭与状态。修改 `services/aos-api/aos_api/main.py` 及相关lifespan测试。默认不开启主库新worker；选项显式启用，依赖runtime host健康。线程安全cancel_event贯穿原Runtime，停止新任务后等待同步执行真实退出，之后才清理共享连接/隧道。超时或结果不明保留unknown，不能虚写executor_stopped。状态接口返回实际进程与数据库事实。
4. Y4d：正式恢复执行请求与界面。复用 `services/aos-api/aos_api/routers/pipeline_snapshot_recoveries.py`、`pipeline_snapshot_schedule_service.py` 及现有配置页面；具体前端文件由页面定位后补全清单。请求只指定exact回执与原幂等键，principal当前授权通过后交同一个受管理worker。不得另起无生命周期管理的后台线程。页面显示停用、可调度、执行中、等待恢复、unknown、需重配；只有实际启用才替换“尚未接通执行”。

## 原组优先与未知结果边界

- 本分钟已有原ScheduleClaim时保留其exact定义/成员身份；同分钟改配置不能创建第二组绕过原回执。
- 跨分钟存在原组running、failed或未知时，不仅检查active Run谓词，还检查完整十二成员和原组完成事实。全失败且stopped也不能直接跳过原组开新周期。
- 原SourceClaim存在而Input未落盘是未知读源结果，禁止重读。Input已保存时只按现有执行窗口或正式RecoveryRef恢复；续期专用定义继续被066围栏禁止新读源。
- 已完成组可进入下一合法周期；当前源权限、控制窗口过期、配置禁用或安装代次不匹配时仍拒绝。不得为周期运行自动放宽24小时窗口。
- worker重启或重复tick不更换原组/幂等键。数据库提交确认未知时先读取原回执，不能重领新的组。

## 验证与退出条件

先Red/Green验证固定分钟身份、配置revision变更、跨分钟未知阻断、普通已完成组下一周期、续期定义不新读源；随后双连接并发同slot、锁竞争、当前权限撤销、disable竞态、停止信号传播和底层线程实际退出。保留旧单路回归、租户负例、卸载禁入及重装代次负例。工厂测试验证原Owner依赖，浏览器验证真实服务状态而非硬编码。

测试均隔离，涉及PG的套件串行。Y4完成后接Y5十二路真实配置、Y6克隆库迁移演练与受控主服务切换，之后Z原业务Run处置及真实经营闭环。任何isolated Green都不计为真实源业务验收。回滚为关闭新增worker入口并保留不可变证据；不删除原Run/Receipt、不回滚用户数据。
