# BG00EQ 共用IPC整帧截止时间

基线AOS-001005/m1@e5060ee7。复习BG00EP：issuer/consumer共用read_issuer_frame，逐recv5秒导致慢速发送每段不足5秒但总耗时可超过5秒。

文件：`services/aos-api/aos_api/aip_network_issuer_ipc.py`仅read函数引入monotonic绝对5秒deadline；header与body共用，每次recv设置剩余时间，完成后再次检查；finally恢复原timeout。帧长、协议错误、身份、消费逻辑不变。

新增`services/aos-api/tests/aip/test_network_ipc_deadline.py`：真实socketpair/线程发送，每1秒一字节共7字节，原实现7秒成功而测试要求拒绝；新实现在5秒附近拒绝（允许调度容差，不篡改时钟）。再证正常分片与原timeout恢复、截断后恢复。sender采用Event与finally join，避免残留线程；不需要正式身份/数据库。先RED，后最小修复，累计issuer/consumer IPC及签名消费回归。

无真实库或服务启动变更，不读商城源/Run，不push；正式OS/身份与首链仍未验收，230 L0挂起。
