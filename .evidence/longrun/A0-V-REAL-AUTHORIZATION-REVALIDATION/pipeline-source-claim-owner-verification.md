# 当前读取占用Owner验证

2026-09-12，m1基线d7eb3cf8。新增pipeline_source_claim_owner.py；reserve/read_current复用exact CurrentControlOwner，安装锁→run锁→当前ScheduleRun/调度/graph/source，旧claim回读也重验。每运行唯一占用、同control调用序号连续且不超过当前maxSourceCalls；事务由调用方提交，服务不读源、不发任务。生产工厂构造claims并共享controls，旧三参数内部服务构造保留兼容。

先缺失模块RED。首次PG运行因一次性夹具只给SELECT，FOR SHARE需要UPDATE而被拒绝；仅修复随机schema夹具权限，正式权限未动。占用/控制Owner/新schema共37 passed，其中两独立连接同时争用一个名额：不同run只一个成功，另一预算拒绝；相同run只一个created=true、另一回读false。覆盖同run不多计、回滚、不同actor、run终态、调度停用、graph revision/source漂移、当前拒绝/被替代、canary、缺claim。工厂及HTTP27 passed；共64项相关验证。当前资产/签名/权限底层仍为明确fake，不当作真实批准证明。

AR2闭包1799/158/93五类错误空，diff check通过；memory验证GREEN/强投影CURRENT。11:29:11Z连续性观察20739秒、341续租、3 OCI running、binding ready/enabled/unfenced@4、canary0；fencedConfigurationProven=false。JSON保留首末事件与完整事件列表摘要，数据库保留全部历史。

主库仍a0v_023，024尚未部署；API仍旧进程，新服务未触发真实审批/占用/源读取。created=true只代表当前事务内新增占用，不是外部可持有的执行许可。后续必须确认提交、再次当前授权；提交未知或旧占用绝不重新发起源查询。独立提交编排、原始批次保存与恢复、禁用旧路径绕过、续期恢复及真实P01验收仍待完成。

下一波：受控读取的独立占用提交与同批次准备；复用现有Ingress和Receipt，恢复不重读。主A0-V Lease继续ACTIVE；m1不push、230 L0挂起。
