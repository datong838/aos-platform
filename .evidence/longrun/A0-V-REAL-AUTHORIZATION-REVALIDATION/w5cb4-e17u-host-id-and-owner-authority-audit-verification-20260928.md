# W5CB4 E17-u｜当前 Host ID 与正式 Owner 权威只读审计

## 实时权威库证据

使用最新 `scripts/a0v_current_preview_http.py:preflight` 当前签名 Receipt 预检获取连接参数后，`psycopg` 连接立即 `conn.read_only=True`，仅查询当前 `org-org/dev-project` 的安装非敏感字段与操作/审批计数；未读商城源。命令退出 0，库 `aos_current_preview_20260927@a0v_109`，安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813`，current revision 3 `approved`、active revision null。`bundle_installation_decision` 当前批准 actor `a0v-current-preview-install-checker` 是安装方案 decision，不是 runtime-apply/enable 或经营动作批准。

精确租户计数：`extension_runtime_operation=0`、`extension_runtime_binding=0`、`extension_runtime_configuration=0`、`extension_runtime_host_assignment=0`、`aip_action_proposal=0`、`aip_action_approval_event=0`、`aip_action_receipt=0`。全库 `extension_runtime_host_identity=[]`。这比 E17-n 的旧快照多确认当前 Host identity 仍不存在；不以零行推论历史 Run 已退休。

## 代码权威路径

- E17-l `scripts/a0v_current_runtime_host_preflight.py` 仅在精确 assignment/identity 且实际 directory role/role OID 对齐后生成 `hostId`。当前无这两张表行，无法得到正向 report。
- `services/aos-api/aos_api/extension_runtime/runtime_directory.py` 的 `RuntimeTenantDescriptor` 只持 scope/assignment revision；`RuntimeHost` 本身无 hostId 字段。独立 `scripts/a0v_ecommerce_runtime_host.py:_serve` 的公开状态仍使用旧字符串 `a0v-local-ecommerce-host-20260912`，与当前权威无关；现有 `main` 在 `_current_preflight` 后固定 `FORMAL_OWNER_AUTHORITY_UNPROVEN`，故目前不会发布 ACTIVE，但解除硬门前必须移除旧状态 ID。
- `LiveInstallationLifecycleOwner` 由 pending runtime-apply 或有效 binding 后在进程内构造；它不是启动前人工 Owner 凭据。安装 preview maker/checker 也不能充当正式操作批准。

## 下一最小波与边界

E17-v 先文件级方案/RED，让独立 Host 运行状态的 Host ID 只来自经 E17-l 校验的当前精确 assignment report，缺失/漂移时安全阻断；Owner hard block 保留。之后需正式三身份、OCI、Host identity/assignment、八配置、操作审批/预算 Receipt 的合法来源，才能讨论空闲 Host 启动和自然首链。当前库只读，Host/worker 0，未碰 dev-org、商城源、旧 12 Run、手工 Run、230 L0。无 `browser-pilot` 新截图。
