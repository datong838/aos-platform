# 失效停用请求失败终结验证

2026-09-13，基线c6ebd051，m1，无push。实现仅对accepted且同generation绑定版本严格前进的旧请求追加失败终态；当前权限、安装etag、operation CAS、tenant、原target与request hash均沿既有_locked校验。binding CAS不放宽，原request/event不变，禁入/资源不修改。执行器第一事务提交失败后返回，不调用drain或第二事务；consumer沿既有终态ACK路径处理。

新增PG测试首轮9失败（入口未实现）。实现后曾有1个测试准备错误：尝试更改历史事件被数据库immutable trigger拒绝；改为篡改测试operation.request_hash来验证原事件与命令不一致，不关闭历史保护。之后21项目标/执行器测试通过，主机+真实签名OCI+consumer 35项通过（10.70秒）。最后新增执行器不进入drain、事务已提交证明，专项10项通过。fixture安装store为受限测试替身，真实Owner/权限与签名资源仍由完整OCI回归覆盖。

清册 ar2-7：1810扫描/158分类/93迁移，五类错误为空。此时旧实际请求尚未通过新代码处理，Host仍停止，新版仍approved。下一步启动唯一新版Host，让原consumer自然消费旧请求为DISABLE_TARGET_STALE；独立回读后才发新当前版本停用命令，保留原key和失败历史。
