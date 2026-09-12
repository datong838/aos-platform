# 配置后未接入卸载验证

完整克隆 aos_config_retirement_20260912，原 a0v_019 基线正例 1 failed/9 passed，复现现场无法卸载。a0v_020 第一候选遇到旧禁用字段的 dispatch_lifecycle 外键；该候选克隆保留为 aos_config_retirement_20260912_initial。正式候选采用独立 unactivated_disable_operation_id，原外键保留，从原快照重新建克隆后 upgrade 成功。

事务回滚的 10 场景通过：合法、未释放资源、未终结操作、成功启用历史、错误配置指针、错租户、错安装修订、缺失禁用证明、binding revision 漂移、epoch 漂移。随后通过真实私有应用身份调用完整 InstallationService.uninstall，提交 uninstalled@6，activeRevision=null；第二次同键重放，524 张公共表内容不变；454 张双租户列公共表的 canary 内容不变。

新回执真实记录配置、正式 disable ID、零成功启用/业务执行；不是旧 never_enabled 回执。所有旧结构约束和真实脱离分支保留，新增仅处理已禁用、无业务历史且完全释放的安装。克隆成功尚不代表主库完成：下一步主库 a0v_020 迁移、同固定请求正式卸载、重新安装和真实配置跨续租启用验证。
