# 重启后运行资源状态投影验证

## UQ6-D2a 资源丢失不再假显示就绪（2026-09-13）

新增runtime_resource_health.py，RuntimeViewReader在同租户只读事务中核对当前generation资源的成功准备记录、容器创建观察、清理状态及数据库时钟租约。原ready但资源证据不足变needs_attention，关闭UI并保留disable；不改任何安装/绑定事实、不重建会话。原非ready流程保持。

43项测试通过，其中实际PG覆盖释放/过期/清理未知/容器或创建记录缺失/NULL期限/混合NULL/失败操作/空集/跨租户项目安装generation拒绝。当前真实安装97aeb2e7-59ba-40f6-89a3-fb0293bc0497的generation3a445eee-aa28-4459-9e5a-f12a806a94b1仍resourcesLive=true，19业务指纹未变；不把租约存活证明当作真实IPC业务成功。

下一切片继续恢复路径：保留当前6606会话，处理active实例恢复/替代计划在产品中的承接；现有preparation-reset不足以覆盖active重启，禁止手工复活旧已投递消息。实际growth1.8发布安装仍需可核验独立审批主体。m1不push、230 L0挂起、总目标未完成。

部署复核：API已以abea5dda重启，PID63144、/v1/health返回ok；IAB重新加载5173/workshop/analyst成功且目录诚实保持不可用。原Host6606持续运行。下波D2b发现配置表单仍要求人工填写ID/revision/hash，将先设计当前代际的可用配置选择接口，复用已有不可变配置及当前四类来源校验，避免手工接线。
