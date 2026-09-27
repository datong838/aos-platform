# W5CB4 E14：运行安装正式入口与当前 Host 准入计划（2026-09-28）

## 上位方案与现场

复习产品 12 栖月汇双侧增长方案、231/231-9 BG-00 及 231-3：用户经产品入口安装、选择授权范围和配置，运行包旧 Apply/Verify 不得绕过隔离生命周期；`runtime-apply` 准备资源但不启业务，`runtime-verify` 在健康/权限/资源同事务核验后才提交 active 和 disabled binding。E13 通用 Apply 得 HTTP 409、原安装仍 approved/3/ETag3、事件3、runtime operation/binding0；E13 verification `2c8ae924` 已冻结该命令，不能在 E14 换键重试旧入口。

当前最新 m1 为 `2c8ae924`，当前命名卷 `aos-a0v-recovery-pg-data`、库 `aos_current_preview_20260927`、schema `a0v_109`。当前 HTTP 8080/Web 8434 可用，18181 关闭，Host/worker 均 0。`scripts/a0v_current_preview_http.py` 是安全预览启动器，硬设 Host=0，并要求安装仍 approved；不能把它当作运行安装工作进程。当前 DB 有历史命名登录角色，但**角色存在不证明当前独立凭据、权限、Host 分配、OCI 和签名制品可用**；无凭据不制造第二身份或用 superuser 代替。

## 本波文件级清单与最小范围

1. 只读审计 `asset_registry/control_wiring.py`、`extension_runtime/{runtime_connections,production_runtime,production_preparation,preparation_worker,preparation_consumer,runtime_view,lifecycle_service}.py`、`routers/bundle_runtime_installations.py`、`scripts/a0v_current_preview_http.py` 和当前卷权限/Host assignment/已部署制品。核对现有正式身份文件引用但不输出秘密；证明当前 Host 0 的具体门及浏览器 runtime 面板的 allowed action。不可用门列为明确产品待办。
2. 对 E13 页面误导，优先在既有安装控制服务与产品面板加**权威的运行包分流信号**，让通用 Apply/Verify 对运行包不再显示可执行，指向同页“运行实例”正式动作；不得凭安装状态、runtime view 的通用 `allowedActions` 或客户端猜包类型。候选文件 `asset_registry/{installation_revalidation,installation_reader}.py`、安装响应合同/路由、`apps/web/src/pages/s2/assetBundles/{InstallationActionPanel,installationActions}.ts*` 及对应测试。实施前确认最窄已有读模型位置，若需新字段则先补契约并做纯内容反证。
3. 若独立 runtime/directory/web 凭据、Host 分配、OCI 与受信制品全都能在**当前卷**核验，再另立可执行子计划和备份，以原产品入口提交唯一 `runtime-apply`，只读跟踪至正式终态；随后才可考虑 `runtime-verify`。若任一不成立，本波只修产品入口/准入诊断，不发任何 runtime 操作，也不启用 Host。绝不用旧 `aos_meta_head` 脚本、当前 `aos_app` 特权账号或临时身份绕过。
4. 专项：后端旧入口拒绝/纯内容保持、前端禁入/指引与旧操作防重、Host 身份门测试；累计相邻回归、TypeScript/构建；浏览器 `/apollo/assets` 安装及运行实例双面验收。代码/方案/数据/越权复审，verification 落盘并提交。按当天最新 m1+当前命名卷完整重启 DB/API/Web，读回身份/版本/端口/页面/功能，再继续 E15。

现场收窄（只读审计后）：当前 `a0v_current_preview_http.py` 明确 `AOS_EXTENSION_RUNTIME_HOST_ENABLED=0`，当前卷 `extension_runtime_host_assignment=0`；不能提交 `runtime-apply` 后留下无 Owner 的未决命令。本波首先交付服务端精确 `RUNTIME_OPERATION_REQUIRED`（HTTP 409、只对运行包的旧 Apply/Verify，保留纯内容原路径）及产品页清晰指引；它是原方案 231-3 已指定的错误语义，不是增加执行许可。文件收窄为 `asset_registry/errors.py`、`installation_revalidation.py`、其专项测试，及 `InstallationActionPanel.tsx` 的提示和测试。若无法由当前安装详情可靠判定包类型，则页面只给通用路径适用范围说明、不通过客户端猜测禁按钮；后续再补正式读模型判别。运行 Host/凭据实操另开后继波，不在本波伪装完成。

## 九步和停止条件

1. 上位方案及 E13 复习；2. 文件级/当前 Host 只读清单；3. 最小产品分流实现（若发现可复用权威）；4. 专项；5. 累计；6. 浏览器；7. 一致性与安全复审；8. verification 落盘；9. 精确提交并进入 E15 当前源/管道/首链配置。任一授权、身份、制品、资源、提交边界不明：停写当前命令，只读对账；不重发、不手工 run_definition、不读商城源、不碰旧 12 Run。保留全部数据卷/备份，230 L0 挂起，不 push。
