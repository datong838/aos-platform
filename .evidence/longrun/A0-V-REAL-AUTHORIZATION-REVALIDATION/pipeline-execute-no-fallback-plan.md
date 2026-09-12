# 手动执行禁入与未知结果不得回退

2026-09-12，基线242e1c1a。复查发现wave_ext.execute_pipeline在execution_mode非live或正式执行异常时走旧内联路径，该路径含无双租户过滤的source查找、直接SQL读源、直接写obj_instance及full删除，违背单写者/隔离/失败恢复目标。当前真实P01为disabled，本波不能让其被旧回退读取。

## 最小封闭方案

- services/aos-api/aos_api/routers/wave_ext.py：统一解析已保存图/内存Owner；未知管道404；已有配置但没有live内控授权409；运行入口异常返回固定脱敏503，不回退。保留已注册live executor的既有委托调用与结果投影；移除整个旧内联SQL执行分支，禁止以HTTP mode/full触发直接删写。读取目录不等于启用。跨租户沿用现有Principal/scope拒绝。
- services/aos-api/tests/test_builds_execute_api.py：用隔离测试数据库和受控fake executor验证未配置/disabled/demo/退役拒绝、冷图恢复仍拒绝、异常只调用一次且无明文/无回退、已启用执行的结果被如实返回、失败不变成功。原测试中要求仅凭metadata就执行/直接写对象的期待废弃；真实数据一致性由ec_durable_executor/Ingress/OTWriter独立测试承接，不能使用mock行宣称业务完成。

## 验证和限制

先红后绿，专项/既有honesty/图恢复/真实调度测试。真实HTTP只对当前disabled P01进行拒绝验收，确认graph revision、builds、schedules不变；不读取业务源，不启动自动化。API实际重启后复验。不新增live授权、不修改source凭据、不恢复旧DDL、不push、230 L0挂起。

正式live委托已有非持久manual结果投影并非完整调度Receipt，本波不声称修复其持久执行控制/审批/预算绑定；下一波需建立正式持久运行控制与现有Ingress调度回执组合，P01实际运行仍未完成。
