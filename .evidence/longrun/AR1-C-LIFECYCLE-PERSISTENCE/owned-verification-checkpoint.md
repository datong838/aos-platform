# AR1-c 持有者验证调度检查点

2026-09-06；m1 基线739000e9 / AOS-000526；沿用主生命周期 Lease。

PreparationOwner 单次接纳内部验证任务，内部全组心跳后生成健康时间；关闭先拒绝接纳，再 drain 任务，最后退出资源上下文。PreparedJob 仅接收 operation/CAS，可信条件 reader 由 worker 构造注入；数据库线程必须 settle 才传播取消。请求取消只停止等待，真实事务结果保留在原操作账本，不冒充未提交。心跳内部不调用 stop，避免循环等待；未决资源异常优先保留。

Red 4 failed（缺少方法）→Owner/Worker 目标25 passed /7.60s；真实签名Registry＋专用OCI＋隔离PG的 signed_worker_verify 1 passed /39 deselected /10.88s，经 job.verify 实际落账。增加线程重复取消及缺失条件拒绝测试后，沿用上一检查点累计命令503 passed /6既有warnings /90.81s /exit0。独立Prime只读复审未发现该增量实质缺陷，未代替测试执行。

无页面代码变化；上一检查点内置浏览器只读冒烟限制继续适用，不声称在线后端已加载本次代码。仅隔离环境，无真实业务写、共享迁移、Provider、计费或发布。安装内部可active但绑定disabled/fenced；正式条件reader、持久派发、配置启用及恢复仍未闭合。新增业务场景0，整波IN_PROGRESS。下一段核对并接入当前权限与共享schema/平台条件读取，不能用测试lambda作为生产许可。
