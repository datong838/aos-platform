# BG00FK 身份来源与投递启动预检

基线AOS-001025/m1@24670633；Task W5CB4-BG00FK-20261001。复习231-5§5/7、418及旧BG00ci身份对账。

## 新鲜只读事实
- API配置仅提供IPC endpoint/attempt目录，consumer进程配置提供DB/OS路径。auth.py从已验JWT的sub解析Principal，无自动签发/刷新或工作负载委托实现。不能以JWT输入参数当后台身份已具备。
- 本仓.env中AOS_NETWORK_CONSUMER_API_CONFIG及AOS_OIDC_ISSUER(S)/JWKS_URL(S)/AUDIENCE非空presence均false；只输出布尔值，未复制秘密。未读取其他外部配置，不能声称全机无正式身份。旧BG00ci是历史线索，不当当前DB证明。
- preflight_consumer只检查a0v120/121/122函数，缺a0v123 claim/finish；CLI serve复用此preflight，因此可能在投递函数缺失或权限漂移时报告ready。

## 文件级最小实现
1. tests/aip/test_network_consumer_config.py新增真实隔离PG参数化负例：claim/finish缺失、SECURITY INVOKER、PUBLIC执行权；错误必须在read-only preflight拒绝，不创建listener、不新增Receipt。先RED证明遗漏。
2. aos_api/aip_network_consumer_config.py只在既有函数检查列表增加两精确签名，复用_function_gate，保持ready/businessAuthorized分离；不改CLI/鉴权/数据库连接。
3. 本plan/verification；专项与config/startup/CLI/连接/私有投递相邻累计，复审、精确commit/Delivery/CAS/419/D-waves。

## 边界与下一波
无迁移，无正式OS/OIDC创建，无服务/worker/Host/Provider启动，当前真库只读。正式自然投递身份仍须合法来源；不可保存人类JWT或让checker/共享API主体冒充原maker。
BG00FL转八配置中预算合法来源/批准与未知费用恢复的独立主线，先依据231与现有预算代码定位具体缺口；不因当前网络身份实例缺权而停全部研发。118到123独立安全恢复波、八配置/Owner/Host/自然首链仍pending。
