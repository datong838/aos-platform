# 025固定部署脚本专项验证

2026-09-13，c2957b89。新增脚本a0v_schedule_control_binding_deploy.py，仅新建独立克隆并正常升级024→025，旧024脚本保留。新表检查3个validated外键（计划/exact批准/自身前序）、强制RLS、immutable双触发器、runtime仅SELECT/INSERT；备份前后检查12个既有表摘要。迁移hash sha256:91b024675bf0b4b7ef814d6f868033c1e5155c3a33f6748111b1e374aac5e5e0。

先RED 5项缺脚本，新增后5 passed：保留备份不可覆盖、迁移hash漂移拒绝、备份漂移拒绝、未知数据库凭证读取前拒绝、失效Lease在环境动作前拒绝。diff检查通过。以上为策略专项测试，真实备份恢复及主库升级尚未执行，必须分别留证。
