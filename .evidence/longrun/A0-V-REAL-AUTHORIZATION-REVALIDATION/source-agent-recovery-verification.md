# 重启后SSH代理恢复核验

2026-09-11，m1 68d1f556。仅核查既有环境：项目.env仅有NIUSHOP_DB_USER/PASSWORD相关键，未读取/输出值；未找到Sequel Ace/Pro既有配置目录，相关数据库客户端应用目录未发现。SSH agent显示无身份。通过系统钥匙串加载本机既有id_ed25519成功，未改写密钥或读取私钥内容。

条件发生变化后，使用BatchMode、StrictHostKeyChecking、10秒ConnectTimeout、单次ConnectionAttempts向既有root@118.195.194.208进行只读认证核验（成功后仅true退出）。返回255，Permission denied。未建转发、未访问数据库、未写远程业务数据；后续不再重复相同认证。真实源尚需服务器接受的既有SSH身份/原连接配置。独立产品开发继续。
