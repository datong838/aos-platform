# 受控本机API启动器检查

2026-09-13，97423c73。scripts/a0v_controlled_api.py固定18181、既有主库和signed roots；API迁移/第二Host/Cron/AIP自动作业/健康维护/SSH预热均关闭。先RED缺脚本，新增后2项策略测试通过（开关覆盖/失效Lease在环境变更前拒绝）。

首次17:56Z检查失败：错误地把Host的Web隔离探针当成完整API身份，要求aos_app成员。保留失败JSON，原API未停。实际只读核查确认该探针无runtime成员权限；原API实际元数据角色aos_app为superuser/bypassrls。修正方案保留本地诊断元数据连接，受控任务仍独立aos_a0v_runtime_20260912→aos_runtime，探针权限不变。生产Web权限隔离尚未完成，不能据此发布。

18:02:29Z实际preflight通过：localDiagnostic=true、productionWebIdentityComplete=false，当前主库、新表RLS、固定roots和PipelineControlServiceFactory可装配；无源调用/Run创建。检查不是启动成功；接下来优雅替换确认的旧PID71247，正常受管启动并验证注册/HTTP/租户边界。所有凭据仅内存读取，无env/命令行秘密。
