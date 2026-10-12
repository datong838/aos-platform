# 当前身份安装网络DNS最小修复

已授权本机身份登录安装发生真实quay.io查询[::1]:53拒绝。主机curl Registry401证明到达，scutil DNS223.5.5.5；VM /etc/resolv.conf为../run/systemd/resolve/stub-resolv.conf悬空链接，systemd-resolved unit not-found，/run/systemd/resolve不存在。没有重叠VM DNS租约，只有不同隔离Docker任务；不夺锁、删除TTL或改全局Colima配置。

仅colima-aos-extension VM /etc/resolv.conf：排他复制原悬空链接到/etc/resolv.conf.aos-before-qyh-20261013，创建0600临时普通解析文件再原子替换并设置0644，nameserver223.5.5.5沿本机真实当前DNS、timeout2/attempts2。保留备份，精确读取前后链接/内容；不安装包、不启动/重启VM或Docker daemon、PG、API、Web，不删除卷或备份。原断链保留可回滚，不自动回滚到已坏网络。成功必须VM真实getent查询quay.io与同一固定镜像实际pull成功；未成功保持错误证据，诊断当前handle。PG来源命名卷/cluster/head与现有健康读独立复核不变。
