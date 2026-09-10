# 既有源连接恢复核验

2026-09-11，基线c7c7a117。只输出配置键名确认.env保留NIUSHOP_DB_USER/NIUSHOP_DB_PASSWORD；未输出或复制值。历史D2.8清册给出本机SSH隧道到原微商城主机，13306/58305当前均无监听。.ssh有既有身份及known_hosts，无config。

一次SSH尝试：BatchMode=yes、StrictHostKeyChecking=yes、ExitOnForwardFailure=yes、10秒连接界限、仅127.0.0.1本地转发、无远程命令。返回255 Permission denied（认证拒绝），未建立隧道、未调用数据库、未读写业务数据。未运行含重置逻辑的旧初始化脚本；未禁用主机校验或尝试密码。

已异步请求此前成功SSH连接的工具/配置位置或由用户恢复原隧道，不索要密码或私钥。真实源缺口现在明确为SSH身份/隧道；已有DB配置尚未验证有效。首链与八工作台仍未完成。独立开发继续：派生命令还会读取当前revision，恢复必须保存原输入/命令而非重算重读。不push，230 L0挂起。
