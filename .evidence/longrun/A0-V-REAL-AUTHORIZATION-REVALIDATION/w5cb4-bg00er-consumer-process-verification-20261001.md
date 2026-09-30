# BG00ER 有限消费者生命周期验证

基线AOS-001006/m1@fbb51bbf。新增冻结ConsumerProcessConfig与有限accept循环，max_connections1..64、accept_timeout正数<=30；可信数据库/路径/UID显式传入，无DB fallback。实际listener由BG00EP身份/路径/外部OIDC门创建，无正式daemon部署。

共享listener目录门0770收紧0750，socket保留0660；不chmod现有目录。退出close，并以parent dir_fd及父目录/目标设备inode/owner/group/mode匹配后才unlink。替换文件或父目录漂移保留，不清理未知对象。

测试过程：缺模块RED99117 exit2；初始权限负例6387/87561表面通过，但/tmp继承gid0而进程egid20提前触发权限拒绝，不能证明目录写权门。只读探针确认目录uid501/gid0/mode0770；测试短路径并显式设gid20、断言全部metadata后，精确RED61576：原0770被接受、1 failed/4.21s/exit1。修复后首轮97736：6 passed/4.40s/exit0。

```sh
services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_network_consumer_process.py services/aos-api/tests/aip/test_network_ipc_deadline.py services/aos-api/tests/aip/test_network_consumer_ipc.py services/aos-api/tests/aip/test_aip_network_issuer_ipc.py services/aos-api/tests/aip/test_network_consumer_signed_https_pg.py --tb=short --show-capture=no
```
累计句柄77471：**56 passed/21.00s/exit0**。真实Unix bind/close、空闲退出、同UID拒绝计数达上限退出；自有socket清理、占用文件/替换文件/父目录替换保留、异常退出清理；无效limit/timeout/相对路径禁止启动。签名HTTPS/PG与两IPC累计通过；git diff --check exit0。

复审：API组只有目录读/遍历而无写，可信服务UID拥有清理权；不声称抵抗同UID/root恶意竞态或macOS扩展ACL，正式部署仍须ACL/身份门。有限接受不等于全进程硬总时限，processed只是服务分派结果计数，不是业务成功。既有0770配置现在fail-closed，需要正式部署调整；本轮没改任何既有目录。测试私有dummy passfile没有真实密码，生命周期测试未连接数据库。

当前真实库只读118、代码122未部署，正式OS/IdP/账号、安装配置/Owner/Host与自然首链仍pending；旧登录403基线债保留。下一波BG00ES先冻结正式消费者进程配置载体与启动预检（只读、精确来源、无参数凭据），再组合启动入口；不可把测试配置当正式authority。m1单写、不push、不读商城源/旧Run、不手工run_definition，230 L0挂起。
