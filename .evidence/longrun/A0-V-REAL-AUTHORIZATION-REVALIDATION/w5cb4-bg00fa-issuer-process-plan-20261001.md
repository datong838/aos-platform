# BG00FA 独立签发进程装配

基线AOS-001015/m1@4575573a，复习231/408、consumer process、issuer IPC/service/connection。Task W5CB4-BG00FA-20261001。本波真库只读、不部署。

## 文件级实现
- aip_private_listener.py：提取既有consumer目录fd/inode/owner检查与清理上下文，仅移除自己创建且父目录未变化的socket；被替换文件/父路径保留。
- aip_network_consumer_process.py：使用共享生命周期，保持既有配置、错误及处理行为。
- aip_network_issuer_process.py：IssuerProcessConfig固定scope、私有credential/attempt及独立OS身份，最多1–64连接、0–30秒accept timeout；先外部OIDC配置/私有目录准入，复用issuer listener、service、连接工厂。decision工厂再次核对scope，不退回API DSN。
- aip_network_issuer_ipc.py：兼容新增expected_scope参数；新进程强制传入。在帧解析后且认证/attempt/DB之前拒绝不同scope。既有组件调用默认None保持合同。
- tests/aip/test_network_issuer_process.py：真实Unix生命周期/异常/替换路径/空闲与内核同UID拒绝；明确替身测试租户拒绝先于DB；不宣称跨OS正向。

## 顺序和范围
RED缺模块，再最小实现、专项/消费者原生命周期及issuer协议相邻回归、复审、verification、精确提交/AOS-Prime同步。无UI变更，浏览器不适用。
本波有界是连接数量、accept和帧deadline；issuer DB目前没有完整SQL/事务总时限，不能宣称总业务耗时有界。后续只读预检/私有JSON/CLI与数据库耗时限制仍需补齐后才考虑正式部署，不用本波启动当前签发服务。
风险：consumer生命周期提取需等价；所有异常退出清理不误删替换文件；process计数不是批准成功。回滚仅精确文件，不删除attempt/业务数据。正式OS/OIDC材料、119–122部署/启动载体修复独立门，Host/worker/Provider继续关闭。
