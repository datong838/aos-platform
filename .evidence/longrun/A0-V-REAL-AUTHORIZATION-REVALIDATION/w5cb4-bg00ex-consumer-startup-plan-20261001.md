# BG00EX API私有配置启动注入

基线AOS-001012/m1@7dfd28de，复习BG00ES私有文件规则、BG00EW应用边界、main.lifespan的启动/清理顺序。不改运行实例或.env。

精确文件：aip_network_consumer_config.py提取既有私有JSON读取为共享内部函数，原load_consumer_config复用，行为保持；新增aip_network_consumer_startup.py和tests/aip/test_network_consumer_startup.py；main.py仅lifespan装配与finally清空network_consumer_config。

新环境键AOS_NETWORK_CONSUMER_API_CONFIG只指向私有绝对文件路径。不存在/空值→None（默认禁入），显式无效→固定StartupBlocked，不降级。JSON exact schemaVersion=1、socketPath、apiUid、consumerUid、ipcGid、apiAttemptDirectory；无DB/password/token/tenant字段。复用16KiB/0700/0600/owner/nofollow/nonblock/fstat/重复键/NaN读取，复用Endpoint及ApplicationConfig；启用配置必须外部OIDC开关正确。此处只验证配置和身份条件，不连接socket/DB，不创建attempt，不启消费者/Host。

main在_lifespan_body（迁移/其他worker）之前加载；启动异常或退出立即清空配置，再走原runtime清理。原create_app签名与未配置路径不变。每次HTTP仍重新认证/私有目录/实际peer，配置加载不构成业务授权。

测试真实私有文件、危险字段/目录权限/相同UID/外部auth错误；无配置兼容；用受控空lifespan body记录顺序并验证失败前不进入body、退出清空。此为装配单测不等于当前正式启动验收。累计旧ES文件/CLI与EW应用/旧健康及必要生命周期回归，RED先行。真实库118只读，119–122未部署，m1精确提交不push，230L0挂起，无商城源/旧Run/manual run_definition。
