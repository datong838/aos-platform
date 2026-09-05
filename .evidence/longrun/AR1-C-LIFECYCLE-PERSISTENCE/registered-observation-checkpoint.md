# AR1-c 注册观察检查点

2026-09-06；AR1-c 进行中，新增业务场景0。

record_registered 在已领取、实际容器ID存在、未释放的精确资源上保存声明hash与包hash等追加事件，同内容重放幂等、不同内容拒绝；复用安装→操作→资源锁序。signed_session 在真实注册比对通过后先提交观察再yield，取消等提交完成后关闭。

PG观察前提/重放/冲突/已释放反证通过；真实签名OCI注册写入故障不yield且回收，独立inspect确认消失；取消观察测试明确提交→关闭且不进入业务调用方。

累计364 passed，6 warnings，49.78秒，exit0，既有JDBC退出日志提示保留。Prime只读复核无实质问题。历史注册观察不是当前存活证明，不是ready/active；下一切片为准备与Installation applied的原子提交。无页面/API变化，浏览器不适用。
