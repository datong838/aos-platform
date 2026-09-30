# BG00EP 消费者私有IPC边界

基线AOS-001004/m1@4097df94。复习issuer_ipc现有kernel peer、Unix listener、帧长及超时；consumer service已有正式JWT/actor/attempt/Receipt闭环。新增`services/aos-api/aos_api/aip_network_consumer_ipc.py`和`services/aos-api/tests/aip/test_network_consumer_ipc.py`，不重写issuer，不开放HTTP。

复用issuer现有Unix peer/listener/framing及严格JSON hooks，不复制底层身份检查。消费者wire只接受schemaVersion/method/payload；method仅inquiry/consume_once，payload是BG00EM精确合同，不能自报UID、DB、凭据、attempt目录或连接工厂。64KiB帧上限。可信进程启动参数提供ConsumerDatabaseConfig、独立consumer UID/API UID/IPC GID、socket绝对路径与私有attempt目录。监听前检查正式外部OIDC配置、私有passfile和attempt目录及现有不同OS UID门；不自动创建身份、修改HBA或读取凭据内容。

一连接只处理一请求，服务返回脱敏status与精确Receipt；异常仅blocked通用码，响应丢失不能再次调用服务或清attempt。重复业务动作由consumer服务持久attempt及DB Receipt负责，不再实现第二份状态机。

先RED合同/真实socket同UID负例、listener禁入、路由单元；正向kernel不同UID需要正式OS供给，不能用合成peer宣称OS隔离已完成。已有HTTPS+PG集成另做累计。发现共用transport问题应单列最小修复，不能以测试替身打开正式实例。当前真实118库只读，代码122未部署，Host/worker/Provider关闭，不读商城源/旧Run、不手工run_definition、不push，230 L0挂起。
