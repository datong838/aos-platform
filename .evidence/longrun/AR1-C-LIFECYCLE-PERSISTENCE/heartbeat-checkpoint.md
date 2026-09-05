# AR1-c 受限心跳检查点

2026-09-06，基线1e36b128 / AOS-000523。SDK额外范围由AR1-C-SDK-HEARTBEAT登记，主AR1-c仍进行中。

复用heartbeat协议类型，注册后仅固定method/32hex nonce，SDK不调用领域handle或业务端口。宿主check_health固定3秒覆盖锁等待与交换、严格回包一致性，失败按原精确监督清理；3秒不包含不能省略的安全回收等待。旧SDK缺心跳时不假装健康。

Red→Green：SDK新心跳1fail/12pass后13pass；宿主方法缺失4fail；锁等待预算反证1fail/4pass，修复后SDK/宿主/真实OCI共23passed10.56s。真实OCI的正常/错误/取消/双取消/闲置stderr五种原路径均插入心跳且继续原调用与回收断言。Prime独立复审无实质问题。

累计沿用preparation-owner-checkpoint.md命令：438 passed，6既有warnings，80.31s，exit0；JDBC既有退出日志问题未改。无页面，浏览器N/A；不改真实业务数据、共享DB、Provider/费用/发布。新增业务场景0。

下一步把健康检查接到平台资源组并形成verify所需当前事实；签名/权限/配置/依赖、正式broker与完整生命周期仍未完成。alive不是ready，不直接推进Installation active或binding enabled。
