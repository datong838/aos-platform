# W5CB4 BG00da｜当前签名安装的准备态 Host 文件级方案

## 上位与问题

231-3 允许 `approved→runtime-apply→runtime-verify→active` 先于配置；E16 要求 API 同进程 Host/assignment 才受理准备命令；BG00cz 证明 E17 Host 预检的“八候选先全有”与当前签名模板来源的 active 要求形成顺序环。本波解除的仅是**准备态 Host 的配置候选前置**，不解除签名、当前物理库、三身份、Host identity/assignment、OCI、操作审批或业务运行门。当前正式凭据/assignment 仍缺，现网继续禁入。

## 文件级设计

1. `scripts/a0v_current_runtime_host_preflight.py`：新增显式 `--preparation-only`，默认完整模式语义不变。两模式都验证当前签名、物理库、三身份、Host identity/assignment 并读取八候选；候选不足时只有显式准备模式返回 GREEN 且报告 `admissionMode=PREPARATION_ONLY`，完整模式继续 `CONFIGURATION_CANDIDATES_MISSING`。报告固定无密钥字段，不授权业务。
2. `extension_runtime/production_runtime.py`：`RuntimeHostSelection` 加不可伪造的精确准备态标记；生产 selector 接收可信组合层显式布尔值，准备态 assignment 只装配安全资源恢复/过期只读 attempt 回收及安装生命周期 scheduler，`consumers=()`，不装配置、停用、UI read 等自然消费。完整模式原样。
3. `asset_registry/control_wiring.py`：只有 `AOS_EXTENSION_RUNTIME_PREPARATION_ONLY=1` 且 E17-l 报告精确匹配准备态才可传标记；缺/错 signed receipt、三身份、物理库、assignment 或坏 flag 一律 INACTIVE。默认完整路径保留现有行为。Host enabled 前置仍在任何 worker 构造之前。
4. `main.py`：准备态仅启动 RuntimeHost task，跳过 product-event、analysis、内容、反馈、snapshot、Cron、logic automation 与 Provider health 的自然 worker 构造/任务；完成态继续原行为。API operation 仍沿 E16 当前同进程 Host、权限/幂等/Receipt 门。
5. 对应 `test_a0v_current_runtime_host_preflight.py`、`test_production_runtime.py`、`test_runtime_startup_composition.py` 先 RED：候选不足准备态接受但业务消费者为0、完整态拒绝；伪报告、错 mode、坏 flag、身份/assignment 失败拒绝；API lifespan 准备态无任何自然 worker 创建。再最小实现与相邻累计。无当前库写入/Host 启动；browser-pilot 若不可用则不记浏览器验收。
6. 复审补充：生命周期 Owner 原本在 verify 后无条件执行 `enable`，目录也会重建已启用绑定。准备态必须只允许 apply/verify：`live_installation_owner.py` 对精确准备态禁止构造 enable consumer；`pending_preparation_directory.py` 对准备态不投递 rehydrate 并将禁入标记传给 Owner；`production_preparation.py` 从可信 scheduler 构造处贯穿标记；`production_runtime.py` 显式传入。先在对应三个测试文件写失败用例，再实施最小改动。完整模式保持原顺序。准备态禁止 enable 执行是本波 GREEN 必要条件。

## 风险与停止门

准备态 Host 可处理真实 `runtime-apply/verify`，但本波没有当前正式三身份/assignment，绝不对当前实例启用。操作仍需独立当前权限、批准/预算 Receipt 与制品核验。任何测试替身正向只证明代码接线；需真实正向证据后才可考虑启动。完整模式不得因准备标记错误而降级准入。
