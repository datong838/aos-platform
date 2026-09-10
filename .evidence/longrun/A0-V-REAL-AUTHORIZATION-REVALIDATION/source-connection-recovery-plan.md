# 既有微商城只读连接恢复

基线c7c7a117。项目.env有NIUSHOP_DB_USER/PASSWORD键；历史qyh_discover_readonly使用本地13306，D2.8清册记载实际隧道58305至既有服务器MySQL。两个端口当前均无监听。.ssh有既有私钥与known_hosts但无config。未读取/输出私钥内容，不运行旧初始化脚本（含重置操作）。

按当前全权开发和真实首链授权，尝试用既有SSH身份、BatchMode、StrictHostKeyChecking恢复仅本地回环转发，不执行远程命令。拒绝未知/变化主机密钥，认证失败不猜密码不循环。成功才用项目已有只读DB配置做只读元数据核验，不修改上游、不复制canary配置。凭据只在内存传入连接，日志只留状态/错误类别。若失败仍可继续独立开发。
