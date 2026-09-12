# 生意探究五角色契约与证据

S01/P01/C06/A02/G06 各沿自身 graph 与隔离 evaluator 通过 7/9/8/6/11 项契约，克隆及主库正式 published r2，历史 r1 保留。A02 初次通用 builder 拒绝，改用既有专用 aip_a02_pilot，前三项提交状态幂等保留。组件 12 测试、既有角色 39 回归通过；各自 frozen EvalContract 使用实际 report.total，不能统一写成六项。

五技能内部用途生成独立 Bundle，原三技能 Bundle 不变。克隆因原三项复核参数遗漏在 claim 后被拒绝，未写错误事实；修复复核前置、同 owner 正式 heartbeat 恢复原 lease，真实 verifiedInternalLicenseCount=5，治理 Task/Run 沿原实例完成。证据组回归 34 passed；后续许可/绑定 24 passed。

契约及证据重放：克隆 524 表、主库 227 AIP 表内容不变，223 租户 AIP 表 canary 内容不变；无新增真实 Provider 调用、经营任务或外部发布。当前这些新增角色尚未激活/绑定。

Host 03:05:30Z 运行 2273.56 秒、37 次续租、三容器存活，同 generation，跨旧约 2200 秒退出时长；仍不是连续多窗或八场景验收完成。
