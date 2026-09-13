# Runtime UI 调用当前身份门禁与 Canonical Router 目标约束

基线 ef87d07e。现有 bridge 只做浏览器通道校验，服务端需另行复核。先交付无副作用合同，不开放 HTTP 业务调用。

新增 services/aos-api/aos_api/extension_runtime/ui_invocation.py：严格固定安装 UUID、安装 revision、generation、epoch、binding revision、精确 route 与 resourceHash。require_current_ui_invocation 将当前 RuntimeInstallationView 与目标逐项比较，要求 ready/enabled/无 fence、当前签名 UI 精确路由和对应 read/command operation claim；只完成前置检查，不产生持久授权。

修改 ecommerce_growth_canonical_router.py 增加可选 ExpectedRuntimeTarget 参数，由可信调用端传入，与 freshly-issued DispatchRef 的安装/generation/epoch 一致才允许交给现有锁定 host port；legacy 分支不能接受此目标。host port 仍在事务内复核 dispatch revision、group、runtime epoch 与业务权限/Receipt，不替换其逻辑。旧调用不传参数保持既有行为。测试目录 tests/extension_runtime，覆盖跨代次/epoch/安装/封锁/未声明操作及 exact 正向/拒绝无副作用。

后续 HTTP 接线还必须复核主体与具体业务命令中的责任人/审批者来源，以及调用点到锁定事务之间签名/权限变化的窗口；未完成前不把门禁判定作为执行能力，不配置通用任意 callback、不直连旧读接口。
