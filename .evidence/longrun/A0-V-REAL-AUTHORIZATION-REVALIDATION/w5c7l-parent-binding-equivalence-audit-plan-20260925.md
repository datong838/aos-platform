# W5c7l Parent Binding 查询等价性审计方案（2026-09-25）

W5c7k 单调 900 秒长测仍超时，`_bound_parent` 2808 次/567.392 秒，Retirement Input `_load` 172 次/516.191 秒。不能凭热点删掉 callback 前后/12 成员的 current 与 running 校验。真实 A0-V closure 仍不获授权。

## 文件级九步

1. 复习 W5c6u–z/W5c7k、上位 231/231-9 与 `_bound_parent`、ControlledIngressJournal、Group/Input/Claim Owner 的调用与事务边界。
2. 本方案先提交；仅新增审计文档 `w5c7l-parent-binding-equivalence-audit-20260925.md` 和 verification，不改代码/DB/索引/部署。
3. 将 `_bound_parent` 拆成 envelope 读回、current claim/控制权、ScheduleRun/Schedule/graph/source 绑定三段；标注每段 RLS、FOR SHARE、事务时钟/锁、错误语义。区分同事务可合并 SQL 与跨 callback 必须重验。
4. 为下一波指定先测再改切片：测试专属透明子段计时与负例矩阵；仅当同事务等价且独立 PG 证明所有失败门仍拒绝，才考虑批量查询或索引，不允许缓存跨 callback/current revision。
5. 跑相关 Host/closure、W5c5k–z/W5c6a–z/W5c7c/e/f/h/j/JDBC 累计回归；测试 PG 用后停。
6. 浏览器只读 rev4 disabled，不保存/运行/冲刷队列。
7. 复审审计与现有代码/计划一致性；不将性能建议写成已实现或授权。
8. verification 提交后 CAS 更新 docs/AOS 上下文与 Prime 独立长记忆并读回。
9. 下一波 W5c7m：先方案，做测试专属 `_bound_parent` 子段透明计时与失败门合同；尚不改生产查询。

旧真实 attempt 不重发、不手工 `run_definition`；商城源行不读，230 L0 挂起，dev-org 零 canary，m1 单写不 push。
