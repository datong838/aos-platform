# AR2-7D D6 停用、卸载与重装联动施工方案

日期：2026-09-10
基线：`aos-platform/m1@b6589cd7`、`docs/m1@682b0ab`
状态：`REVIEWED_IMPLEMENTATION_PLAN_D6C_NEXT`

## 1. Rules 与边界

- 以 closure manifest、231-6 D6/C10/J04/J06/J07/J11 和 D5C 已封存权威为准；m1 单人串行，方案先于代码，每切片专项、邻接、全量、证据和提交后自动进入下一片。
- D6 复用现有 `extension_runtime` disable、资源 ownership journal 和 Installation immutable transition；只新增受控从属联动，不复制第二套安装生命周期。
- D5C2 只用于 resume 前的结构验证失败。activation 已 `resumed` 后必须走 D6 disable → dispatch detach → resource release → uninstall，禁止把 validation rollback 当卸载捷径。
- 所有实现与测试保持 no-effect：只用隔离 PostgreSQL、仓内签名测试制品和隔离 OCI；不连接真实源、不调用 Provider、不产生费用、不执行共享/生产迁移、不做真实租户装卸、不 push。230 L0 继续挂起。

## 2. 当前缺口

1. 通用 disable 已能先提交 runtime fence、增加 execution epoch、排空 generation attempt 并落 `disabled`，但不会同步暂停该 installation/generation 对应的 cutover claim gate，也不会撤销九项 extension dispatch。
2. activation 已 resume 时，D5C2 正确拒绝 rollback；仓内尚无专门的 post-resume detach authority。因此 runtime 虽能拒绝 handler，occurrence 仍可能被 open gate 领取，九项 dispatch 也仍指向已停用 generation。
3. Installation `uninstall` 当前可从 active 直接写不可变安装 revision；它尚未要求 runtime disabled、九项 dispatch 已撤销、当前 generation 的资源/slot/subscription 已确认释放。
4. 现有 ResourceJournal 能保存精确 OCI ownership 并以确认观察标记 release，但没有把“本代资源全部 released”绑定到 uninstall transition；重装的新 installation/generation/epoch/group revision 与旧权威隔离也缺联合证明。

## 3. 串行切片

### D6A：disable 与九项 dispatch detach 原子联动

- D6A1 先交 `ar2_017` 与 `EcommerceGrowthDisableDependent` 的事务内 authority/readback，直接以既有 runtime disable operation 验证 fence/detach、Receipt 和 9/9 CAS；D6A2 再把该 concrete dependent 注入 disable service/executor/consumer/production wiring。两笔都未通过前不声称 disable 已自动联动。
- 接续迁移 `ar2_017_ecommerce_growth_disable_detach.py`，新增从属于既有 runtime disable operation 的 lifecycle authority、不可变事件/Receipt 与两个受限固定函数。
- 在通用 disable 的两个既有事务边界加入受信 dependent hook：第一事务先由现有 `RuntimeBindingStore.fence` 关闭 runtime 并 epoch+1，同事务锁定 resumed activation、把 open gate 改为 paused、把 9/9 extension dispatch 整组设 fence；第二事务在既有 generation drain 成功后，把 9/9 整组恢复 activation prepare 的 legacy identity、删除 gate，再允许 disable operation 成功。
- dependent 只能由 production-owned concrete wiring 注入；没有匹配 resumed cutover 时严格 no-op，既有非电商 disable 行为不变。任一 hook、Receipt、9/9 CAS 或当前权威失败，所在事务整体回滚；第一事务已提交后第二事务失败时继续保持 runtime/gate/dispatch fence。
- 覆盖 normal/replay、9/9→0/9、并发 claim/attempt、UNKNOWN 只对账、旧 epoch/generation、跨租户、非特权、直接函数缺 Receipt、宿主重启与非电商 no-op。

### D6B：资源释放与 uninstall 前置门

- 新增受信 uninstall orchestration，先读取已完成 disable/detach Receipt，再按 ownership journal 逐个回收本 generation 的 OCI/slot/subscription 资源；任何 absent/unknown 观察都不算 released。
- `InstallationService.uninstall` 的生产 wiring 注入当前 runtime uninstall guard；有 runtime members 时只允许 exact disabled binding、dispatch detached、全部资源 released、无 claimed/running/UNKNOWN 未归宿义务后写 installation `uninstalled` revision。普通内容包和无 runtime member 的既有流程保持原合同。
- 卸载提交把 binding 推进为 desired `uninstalled` / observed `stopped`，但保留 Case/Receipt/审计只读历史；资源或权限漂移保持 fail-closed，不用删除历史冒充释放。

#### D6B 细化施工卡（2026-09-10）

- D6B1 新增 `extension_runtime/runtime_uninstall.py` 的固定 cleanup executor。每次只处理一个 ownership lease：第一事务锁定 installation、最新 generation binding、成功 disable operation、D6A detach Receipt 和 resource identity，写 cleanup intent checkpoint 后提交；事务外只允许 `CleanupOnlyOciDriver.remove_owned`；第二事务用既有 `ResourceJournal.record_cleanup` 写真实 removed 观察。引擎异常、absent/false 或进程重启一律保持 `uncertain/observed_release=false`，不自动重发未知删除。
- D6B1 扫描限定 exact installation + generation + engine context，稳定按 resource_id 分页；已 released 幂等跳过。禁止复用“过期 preparation recovery”冒充主动卸载，因为 uninstall cleanup 必须以成功 disable/detach 为当前授权，与 lease expiry 无关。
- D6B2A 新增 `ar2_018` 窄卸载 authority 与 `RuntimeUninstallGuard`。Web 数据库身份 `aos_app` 不获得 runtime 表的通用读写权；只可执行 tenant-scoped `SECURITY DEFINER` 命令。命令在既有 installation 锁与同一事务内只接受唯一 generation binding、binding desired=disabled/observed=unknown/enabled=false/fence=true、对应 disable succeeded、D6A lifecycle detached 且 fence/detach Receipt 均可回读、该 generation 至少一项 lease 且全部 released、occurrence claimed、dispatch attempt claimed/unknown、runtime attempt running 三类义务均为零、九项 dispatch 已恢复 legacy 且 gate 已删除；随后原子写不可变 runtime uninstall Receipt，并把 binding 推进到 desired=uninstalled/observed=stopped，保留 fence并 revision+1。Receipt 的 authority_data 与数据库内 SHA-256 由 deferred constraint 绑定，缺 Receipt 或内容漂移不能提交。
- D6B2B 由 `InstallationService._append_uninstall` 在 leaf guard 后、installation revision 前调用 concrete guard；普通无 runtime binding 的内容包严格 no-op，存在 runtime authority 但事实不全时 fail-closed。canonical HTTP `build_installation_service()` 与 `build_runtime_control_plane()` 内部的 InstallationService 都必须注入同一 concrete guard；只改 runtime control plane 会留下 HTTP 绕过。测试构造保留可选参数以兼容既有隔离夹具。runtime guard、binding 终态、installation event 任一失败都回滚同一事务。D6B 不删除 resource lease、operation、Receipt、Case 或 audit 历史。

### D6C：重装代次与旧权威隔离

- 重装必须创建新的 installation 与 generation，enable 产生新 execution epoch，重新 prepare/cutover 产生更高且独立的 group revision；不得复活旧 installation 的 Approval、claim、DispatchRef 或 idempotency scope。
- 联合测试证明旧页面请求、旧 epoch/generation、旧 approval/ref 和旧 target Receipt 全部拒绝；旧 Case/Run/Receipt/审计仍按原 tenant 只读，新代次只有经完整签名、配置、健康、cutover validate/resume 后才可派发。

#### D6C 细化施工卡（2026-09-10）

- 当前 generation 由 `build_plan` 服务端生成，RuntimeOperation 唯一键包含 installation，运行接纳和九项 HostPort 均复核 installation/generation/epoch，cutover 对共享九项 dispatch 使用单调 group revision；D6C 先以同租户、同 package digest 的联合 PostgreSQL 证明复用这些既有权威，不先新增第二套重装状态或迁移。
- 旧 installation 完成 D6B 终态后，创建全新 installation 与 generation，按新 binding 独立产生 epoch；在原 cutover group 的 9/9 legacy 行上以更高 expected/target group revision 重新 prepare→commit→validate→resume。新 cutover 必须使用绑定新 target 的新 Approval；旧 Approval 因 proposal payload/target/hash 不同而拒绝。
- 固定保存旧 DispatchRef 后再切新代：旧 installation/generation/epoch/dispatch revision/group revision 任一复用都必须被 HostPort 当前事务校验拒绝；旧 operation/idempotency Receipt 只能在旧 installation scope 回读，不能驱动新 installation。新代九项必须全部指向同一新 installation/generation/epoch/group revision，不允许半组。
- 卸载前后的旧 runtime operation、disable/detach/uninstall Receipt 与 installation revision 保留且同 tenant 可读，跨租户继续不可见。若联合反证发现既有锁或 hash 未覆盖某一旧权威，再新增最窄 guard；若全部通过，D6C 只提交测试、证据与必要的可复用测试夹具，不为“有代码量”修改生产路径。

### D6D：同 digest 隔离联合验收

- 以一个仓内签名 ecommerce-growth 制品，在允许的隔离 OCI 完成 install → verify/configure/enable → 9 项可派发 → disable 禁入 → 9 项拒绝 → resource release → uninstall 不可见 → reinstall 新代次可派发。
- 固定记录 image/package digest、installation/generation/epoch/group revision、每阶段 Receipt、OCI 资源观测和失败注入；不得用 mock 容器结果冒充物理释放。若当前引擎不满足 userns/seccomp，代码与 PostgreSQL 切片继续完成，D6D 明确保持 blocked，不降低隔离门。

#### D6D 细化施工卡（2026-09-10）

- 预检固定使用 `colima-aos-extension`；必须由 `OciDriver.require_isolation()` 实测 Linux、userns、seccomp，并先通过真实 registration/cleanup/seccomp 用例。任何一项不满足即停止 OCI 动作并记录 blocked，不切到默认 Docker、不取消安全参数。
- D6D1 在 D6C 完整 PostgreSQL authority 链上把 mock resource 替换为真实 `OciDriver.create_session` 结果：持久化 exact image/config digest、平台生成 name/owner 和 64 位 container id，先独立 readback 运行/ownership/security 参数，再走 disable/detach 与 `RuntimeUninstallCleanupExecutor(CleanupOnlyOciDriver)`。删除后必须由独立 `docker inspect` 得到 absent，lease 同时为 `released/observed_release=true`；unknown、owner 或 container-id 漂移均不重发且不得进入 uninstall。
- D6D2 新增专用 `test_ecommerce_growth_signed_lifecycle_pg.py`，复用现有仓内签名 Registry、offline registry、PreparationWorker、verify/configure/enable 和完整 AR2 cutover authority。第一代必须在同一 tenant/schema 内完成签名 install、真实 OCI running、9/9 extension resume、disable fence 后拒绝、9/9 legacy detach、物理 release、runtime/installation uninstall；随后用完全相同的 signed package/image digest 创建第二个 installation/generation，重新 verify/configure/enable/cutover 并证明 9/9 可派发。
- 全链保存第一代 Approval、DispatchRef、validate Receipt、operation idempotency key 与 container id，在第二代逐项反证旧 authority；同时回读第一代 installation revision、runtime operation、cutover、disable/detach/uninstall Receipt。测试 teardown 必须按 exact owner/container id 清理所有 OCI container、临时 registry/image/schema，并独立确认无 `aos.extension.owner` 残留。
- D6D1 与 D6D2 都通过后才允许结论 `AR2_7D_DISABLE_UNINSTALL_REINSTALL_GREEN`。若 D6D2 需要扩大 production 数据库角色或复制生命周期实现，先停止编码、更新本卡并拆出最窄实现方案；不得在测试里给 production role 补临时通用权限后声称完成。
- D6D2 冷启动预检发现 `offline_registry.py` 的约 59MB 本地镜像连续超出固定 60 秒 pull 门。请求日志证明 Registry 只收到宿主健康检查、daemon 未发出 manifest/blob 请求；干净重启专用 Colima 后现象不变，排除 Registry 单线程与遗留 pull 锁。进一步探测确认用户级 Docker 配置仍指定已停止的 Docker Desktop credential helper，localhost 凭据查询在 5 秒内不返回，因而 `docker pull` 在访问离线 Registry 前阻塞。最窄修正限定在测试 fixture：保持原 Registry 只读 GET/HEAD、localhost 映射、固定 digest 和 60 秒门不变；pull 使用临时空 Docker 配置并通过目标 context 的 exact daemon endpoint 连接，既不改用户全局配置，也不启动 Docker Desktop。以 signed worker configuration 实测通过、teardown 无 Registry/owner 残留为退出条件。

## 4. 文件上限

- 新增：`services/aos-api/alembic/versions/ar2_017_ecommerce_growth_disable_detach.py`、`services/aos-api/alembic/versions/ar2_018_runtime_uninstall_authority.py`、`services/aos-api/aos_api/ecommerce_growth_lifecycle.py`、`services/aos-api/aos_api/extension_runtime/runtime_uninstall.py`、`services/aos-api/tests/extension_runtime/test_ecommerce_growth_signed_lifecycle_pg.py`。
- 最小修改：`services/aos-api/aos_api/extension_runtime/{disable_commit.py,disable_executor.py,disable_service.py,disable_consumer.py,production_runtime.py}`、`services/aos-api/aos_api/asset_registry/{control_wiring.py,installation_service.py}` 及其直接测试。Router 只在生产 service wiring 必须切换时修改。
- 不修改领域 bundle 业务实现，不扩写八工作台 UI，不改变预算/Provider/真实数据权威。发现额外文件依赖先更新本方案与 231-6，再编码。

## 5. 验证与退出

- 每切片：新 PostgreSQL 专项、既有 disable/lifecycle/production host/asset uninstall 邻接、compile、diff check、Alembic 单头、closure、memory validate。
- D6A 后运行完整 `tests/extension_runtime`；D6B/C 增加 asset registry uninstall/replacement 全量；D6D 增加真实隔离 OCI 观察。
- D6 退出必须同时具备：同 digest 安装启用、九项派发、停用先围栏、排空后 9/9 legacy detach、资源确认释放、卸载、重装新代次、旧权威拒绝和历史只读。唯一切片结论为 `AR2_7D_DISABLE_UNINSTALL_REINSTALL_GREEN`，随后进入 AR2-7D 剩余可插拔累计验收；不提前宣布 AR2-7 或 7E 完成。
