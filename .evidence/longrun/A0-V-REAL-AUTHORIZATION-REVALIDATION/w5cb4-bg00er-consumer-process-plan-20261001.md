# BG00ER 消费者可信配置与有限生命周期

基线AOS-001006/m1@fbb51bbf，复习BG00EP/EQ。现有仅listener/serve_one，无生命周期。目录0770允许API组改动socket路径，自动退出清理不宜建立于此。

文件范围：共享`services/aos-api/aos_api/aip_network_issuer_ipc.py`仅socket目录门0770收紧0750（socket仍0660），不自动chmod既有目录；旧0770配置明确拒绝。新增`aip_network_consumer_process.py`与`tests/aip/test_network_consumer_process.py`。

冻结进程配置：socket绝对路径、不同API/consumer UID与IPC GID、固定ConsumerDatabaseConfig、私有attempt目录、max_connections(1..64)、accept_timeout(0..30秒，正值)。无wire配置、无环境DB fallback，不创建账号/凭据/目录。run函数有限接收，拒绝连接也计数，空闲timeout退出；服务已具有帧/数据库边界，不宣称全进程硬总时限或Supervisor部署完成。

生命周期关闭listener；清理使用已打开parent dir_fd，父目录仍是同设备/inode/owner/group/0750、socket仍同设备/inode/socket类型/owner才unlink。替换文件、父路径漂移、占用路径不删。模型是服务UID可信、API组无目录写权；扩展ACL/宿主权限仍需正式部署门，不声称抵抗同UID或root并发恶意修改。失败启动保留未知现场而不猜删。

先真实Unix文件权限RED，后最小生产代码；实际bind/关闭/清理/占用保留/替换保留/同UID禁入/空闲退出/有限接受；正向跨UID业务仍无正式证明。当前库只读、不启动正式进程，不读商城源/旧Run、不push，230 L0挂起。
