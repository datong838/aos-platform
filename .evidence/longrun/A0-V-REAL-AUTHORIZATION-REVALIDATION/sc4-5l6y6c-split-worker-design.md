# Y6c 独立Host下的快照调度器托管

2026-09-16，主库066，基线3e0bc261。先方案后编码；单写m1、不push、230L0挂起。现有Host12960保留，不重启/退役J。

## 已核实边界与决策

RuntimeHost.stop→LiveInstallationScheduler.stop→LiveInstallationLifecycleOwner.stop→PreparationConsumer.stop→PreparedJob.stop清理原资源。committed_cleanup明确已验证代次释放后必须围栏，preparation_reset拒绝已有binding或已验证安装。故前波统一进程方向不适用于当前J的无损接续，予以替代，不实际停止Host。

快照PipelineSnapshotScheduleRuntime直接组合原Ingress/Completion/Store，不调用或持有PreparedJob。执行许可由run_guarded及十二路Owner在事务内核当前安装/代次/epoch/签名锁、权限、共同窗口、额度和回执；停止/卸载后的binding fence仍拒绝。它可以由API独立托管，事件由已有Host消费，无需第二Host。调度器活着不是安装可执行或业务完成，runtime状态接口已有executionAuthorized=false。

新增显式部署选项 AOS_SNAPSHOT_GROUP_WORKER_TOPOLOGY，取值cohosted（默认，保留原健康依赖）或 independent（独立数据调度，不要求本进程Host）。未知值fail closed；independent仍要求原PipelineControlServiceFactory，Store由原上下文创建，原stop/drain覆盖同步线程；不新增执行入口、不跳过任一执行Owner守卫。independent可在没有enabled definition时安全空转。Host是否健康不由此选项声明；API状态仅报告本调度器的真实Task/worker状态，不虚构extension_runtime_host_task。

## 文件与验证

修改 services/aos-api/aos_api/main.py 的 _start_snapshot_group_worker，新增应用状态snapshot_group_worker_topology并按选择传生命周期依赖；原cohosted行为保持。修改 routers/pipeline_snapshot_schedules.py 的worker状态：independent只检查自身task，cohosted同时检查真实hosttask；未识别模式不可用，租户隔离不变。扩展 tests/test_snapshot_schedule_main_lifecycle.py、现有snapshot schedules HTTP测试，覆盖缺Host默认拒绝、显式独立可启动/无伪Host、无factory拒绝、未知值拒绝、停止等待实际thread、跨租户不可见。原权限撤销/安装停用guard回归必须通过。

新增 scripts/a0v_snapshot_product_api.py：只封装原event_complete API profile，固定independent+worker enabled，保留原Host关闭、迁移关闭、其它后台任务关闭；不修改旧启动器默认值。配置本波无enabled definition，真实启用只验证受管理空转，源Run/Claim计数必须不变。API重载仍只动61700，Host12960继续持有原锁和资源；新脚本单例沿用18181端口并独立API锁，不能旁路原Host配置。明确不将本进程host disabled当作错误。

本波只接托管，Y5d十二路当前审批、组定义和真实执行随后；不会自动为expired控制续期、不触发旧业务Run。部署前补实际launcher测试与状态观察依据；主进程监听不等于worker已启动，必须日志/受保护runtime状态确认。

launcher细化：原load_launcher返回独立模块，仅在其API_FLAGS添加snapshot enabled/independent和TWA pg；检查旧Host关闭等固定flags未变。serve前独占本波API锁并检查当前Y6c lease，端口仍18181。包装原lifespan只观察实际app.state（不创建假任务）：启动后必须snapshot task存活、scope正确、无本进程host task，保存私有带pid/observedAt的状态；退出在原lifespan实际清理后记录STOPPED/FAILED_CLOSED。此状态是进程观测，不是执行审批。脚本测试覆盖默认profile不被污染、锁竞争不启动第二API；部署后核原Host12960存活和J原binding/资源不变、定义数0、源Run/Claim零新增。

守卫补充文件：services/aos-api/tests/extension_runtime/test_snapshot_schedule_runtime_pg.py 增加已安装binding显式禁用/围栏后拒绝原Runtime、零source调用/零Run测试。此测试直接覆盖独立调度依赖的原最终授权门，不以应用启动成功代替禁入。首次累计命令误未排除耗时full Store黄金例，隔离过程SIGINT后12项已过但整套未完成，不计整套通过；后续精准排除该未改动黄金例，运行其余守卫及原撤权恢复回归。

验证修正：runtime_case 的 service 明确以 named_assets 替代安装资产守卫，不能证明安装围栏；新增测试因此无效并已移除，其隔离运行已中止，不计通过。改为原 test_runtime_gate_pg.py 上直接覆盖 enabled=false 与 operation_fence=true 各自独立拒绝，原真实PG binding锁/安装baseline seam范围保持明确。用原门禁回归与原Owner调用路径审查组成证据，不宣称全链真实安装禁入演练。

原库约束禁止 enabled=true 且 operation_fence=true；负例改用两种合法禁入状态：disabled无fence，以及disabled且fenced，保持原数据库约束。先前非法组合的CheckViolation不计门禁测试通过。

## 收口证据与限制

实际API PID64525、18181健康；私有status持续刷新、worker IDLE/alive、independent、hostInThisProcess=false，加载三文件hash与工作树一致。J原generation/epoch/binding不变，资源3份held未释放；主库066、definition0、12调度disabled、source run11/claim10不变，详见y6c-independent-worker-verification.json。

40 lifecycle/HTTP/launcher passed (5.83s)，21 targeted guard/runtime/recovery passed、1未改动Store黄金例deselected (66.05s)，原runtime_gate真实PG 9 passed (4.06s)。安装baseline在该底层门禁测试中为显式seam，绑定/锁/围栏使用实际PG；未声称完整线上卸载演练。测试中止/错误记录保留：首次累计误入耗时黄金例中止、无效fixture禁入测试中止、缺测试DSN导致setup失败、非法enabled+fenced组合被DB约束拒绝，均不计通过。

方案复核：默认cohosted不变；independent仅解除同进程Host存活前提，仍由原Factory/Owner执行所有授权。没有第二Host，没有自动审批/打开旧窗口，没有历史数据伪装快照。部署launcher受本波lease限定，未来重启须以新当前部署lease恢复，不能把本波完成receipt当长期启动授权。

下一波Y5d：补十路live ingest descriptor（保持disabled），十二路当前selection/control/binding同窗口审批、组定义disabled登记与原键读回；在明确组与窗口后独立波次启用并观察真实12源执行。Z旧业务Run恢复及经营首链/八工作台均未完成。
