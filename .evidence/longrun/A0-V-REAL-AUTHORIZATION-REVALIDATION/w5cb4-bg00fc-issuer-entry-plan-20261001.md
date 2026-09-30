# BG00FC 签发配置与显式入口

基线AOS-001017/m1@88a2dca2；复习231/410、consumer config/CLI、issuer process/connection及118保护触发器。Task W5CB4-BG00FC-20261001；不部署当前实例。

## 文件级最小方案
- aip_network_issuer_config.py：复用_read_private_config的16KiB/owner/0700/0600/no-follow/非阻塞/重复键检查。exact schemaVersion/socketPath/apiUid/issuerUid/ipcGid/database/scope/attemptDirectory/maxConnections/acceptTimeout；scope仅orgId/projectId，database仅host/port/database/passfile，禁止密码/角色覆盖。
- preflight_issuer：预期TenantScope必须等于私有配置scope；复验当前OS、外部OIDC配置形状、私有attempt/socket目录与空闲路径；仅connect_issuer_read_only核验真实DB登录/作用域/超时，查询两个118触发器的enabled/type/目标函数及函数invoker/search_path结构。不写业务、attempt或socket。ready并非正式签名/身份/HBA全部证明，businessAuthorized=false。
- aip_network_issuer_cli.py：复用consumer CLI私有Parser/Once，--mode check|serve、--config、--preflight-org/project均显式且不允许重复/缩写；错误固定脱敏，参数exit2、准入exit1，成功JSON。serve预检通过后才run_issuer_process，无自动部署或无限循环。
- tests/aip/test_network_issuer_config.py、test_network_issuer_cli.py：真实私有文件、隔离PG/触发器漂移拒绝、真实子进程check与idle serve；scope不符/占用路径拒绝；import不加载Web；Event/Proposal/Receipt计数不变。

## 验收和边界
RED缺模块、最小实现、专项和consumer配置/CLI及issuer进程/启动累计；复审/verification/精确提交、Delivery/CAS和Prime回读。临时issuer登录复用BG00FB夹具并复原，不造当前正式身份。仅idle serve非跨OS正向业务；无UI变化。配置和程序结构预检不是整个部署批准，当前库只读、119–122部署与启动载体恢复仍独立门；未知不重发，不读商城源/旧Run/manual run_definition/Provider/230L0，不push。
