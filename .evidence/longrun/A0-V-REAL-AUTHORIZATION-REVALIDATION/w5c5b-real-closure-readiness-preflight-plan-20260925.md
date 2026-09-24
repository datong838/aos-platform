# W5c5b 真实关闭只读预检分层方案（2026-09-25）

上位 231 A0-V/231-9 BG-00；W5c4t 已有严格 24h/组身份/effects 分类，W5c5a 已有隔离 SQL 正反事务测试。真实组仍未到时。本波只增强**只读建议**，不把预检变成关闭命令。

## 文件级九步

1. 复习 `scripts/a0v_w5c4t_closure_feasibility.py`、正式 `a0v_091` SQL/Service、W5c4s/r 失败及定义禁用证据。
2. 文件清单：本方案；新增 `scripts/a0v_w5c5b_real_closure_preflight.py` 与 `services/aos-api/tests/extension_runtime/test_a0v_w5c5b_real_closure_preflight.py`；本 verification。既有 W5c4t 不改、正式 Owner/迁移不改。
3. 最小实现：复用 W5c4t DB-clock 只读观察，再只读核精确 disabled definition 下全部 schedule off、唯一 group/12 Run、固定关闭 key 与 Receipt 仍 0、actor 当前 admin、当前 DB 角色仅作可用性提示、Host/18181 进程拓扑单例；任何缺项冻结，资格到时只输出 `REQUIRES_SEPARATE_REAL_CLOSURE_PLAN`、绝不调用 Owner。不得打印敏感来源行或凭 pid 文件推断进程。
4. 专项覆盖早于/等于 24h、身份/权限/拓扑漂移、key 已存在、到线也不自动行动；只允许只读数据库/本地进程检测。
5. 有界累计 W5c3–W5c5b 与相关合同测试，隔离库若用则停用。
6. 浏览器只读计划/整组页，不能代替数据库/进程门禁，不碰运行/保存/队列。
7. 方案/代码一致性与风险复审：观测可能竞争，任何 GREEN 只代表采样瞬间；实际关闭前独立方案和实时串行事务内再次验证，未知提交边界冻结。
8. verification 落盘提交后 CAS 同步 docs/AOS 项目开发上下文与 Prime 独立受管记忆，读回。
9. 下一波 W5c5c：补齐只读门禁证据或并行安全研发债；到严格 24h 后另立真实执行方案，唯一原 Owner 动作、独立审计、正式退休。

m1 单写不 push；商城源行不读；旧 attempt 不补跑；dev-org 零 canary；230 L0 挂起。
