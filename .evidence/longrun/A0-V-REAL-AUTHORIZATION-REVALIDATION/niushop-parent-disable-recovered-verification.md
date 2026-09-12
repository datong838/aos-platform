# 旧版停用故障实际恢复完成

2026-09-13，RuntimeHost v16 PID21028，代码2b2ab503，新1.5完整签名根，唯一Host。原v15不存在，不再发送TERM。旧资源均已释放。

原操作 e578ff09-b0ba-4de8-979e-ee4f7e13d6a3 被既有consumer自然处理为failed@2、DISABLE_TARGET_STALE，原请求binding@4及事件保留；未修改原target或复用key。补充固定disable-parent-recovered命令只认旧ID/active@7、指定generation/binding@5禁入unknown，原失败码及所有资源释放必须当前读取证实。测试1 failed/23 passed→24 passed，增加未知结果/其他失败/资源未确认的前置拒绝后28 passed。

新请求 cd6d0bd1-d52d-4847-b18c-77a4588f3a87 使用新的命令文件和key，实际succeeded@6。旧binding@7/epoch5、enabled=false、fenced=true、desired=disabled、observed=unknown。生产require_predecessor_drained当前读取通过，精确disabled_committed/hash/epoch均成立。该事件resourcesRetained表示disable本身不执行资源删除；资源实际已在前一故障清理释放，不能解读为仍有容器运行。

新实例 eda57424-b8cb-401e-a6f7-94220cb4f9ef仍approved@3、无运行资源。旧安装历史active@7保留作为replacement exact predecessor，不uninstall绕过lineage。旧P01数据/Receipt和源配置未改。下一波新实例prepare/verify/configure/enable，API仍旧版，商品首读及自然经营链未完成。
