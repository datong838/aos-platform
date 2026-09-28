# W5CB4 E17-u｜独立 Host ID 与正式 Owner 权威只读审计方案

## 已复习

231-3/E17-n 区分安装 decision actor、运行操作审批和进程内 `LiveInstallationLifecycleOwner`。E17-l 报告包含精确当前 `hostId`，但独立 Host CLI 的公开运行状态仍写死 `a0v-local-ecommerce-host-20260912`。`RuntimeHost` 对象本身不承载 hostId，目录只读函数只给 scope/assignment revision；当前 CLI 入口在预检后固定 `FORMAL_OWNER_AUTHORITY_UNPROVEN`。不能用旧 Host ID、preview checker 或进程 Owner 对象解除硬门。

## 本波只读动作

1. 当前签名 Receipt 预检、代码路径和当前权威库的只读查询：确认安装 current/active revision、正式 decision、runtime operation/binding/configuration、精确 Host assignment/identity、Action approval/receipt 的当前行数；不读商城源或敏感负载。
2. 追踪独立 CLI 的 `_current_preflight`、`_serve` 状态写入和 E17-l report 的 hostId 来源，列出未来正向 Host ID 绑定必须满足的条件与最小文件点。若无合法 authority，保持 hard block，不编造正向。
3. 落盘 verification、D-waves 下一波文件级清单、上下文和 m1 精确 docs 提交；不启 Host/worker、不写当前库。后续若选择代码修正，先另波 RED。

## 出口

只读事实能支持“当前缺哪些正式权威”和“旧 Host ID 状态风险”的结论；不能支持 Host/首链已成。下一波应先修准确的状态 Host ID 绑定和正式 Owner/审批合同，再考虑空闲 Host 启动条件。
