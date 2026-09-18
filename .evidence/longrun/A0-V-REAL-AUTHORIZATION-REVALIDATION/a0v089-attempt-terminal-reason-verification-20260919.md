# a0v089 attempt 终态原因持久化验证

## 1. 结果

- 代码迁移 head：`a0v_089`，单一 head。
- 真实恢复库尚未迁移；Runtime Host 尚未重载；没有产生 successor、商城读取、Store 写或模型调用。
- AM 两笔历史 failed 行继续保留 unknown/null，不追填推测原因。

## 2. 实现边界

- attempt head/event 增加 nullable `terminal_reason_code` 与 `terminal_error_type`。
- a0v089 后的新 failed transition 必须带固定 reason；succeeded/running 必须为空；abandoned 固定为
  `ATTEMPT_LEASE_EXPIRED`。
- event 必须在同一事务匹配 head 的 state、revision、reason 和 error type。
- recoverable context 区分 heartbeat stop timeout、heartbeat renew/race、ingress cancelled、ingress deadline 与
  其他 execution exception；heartbeat 安全失败优先。
- 只保存经过 ASCII/长度约束的异常类名；不安全类名退化为 `Exception`，从不保存异常正文。
- signed-read 沿用自身已验证的固定 failure code，不改变 UI request 的状态机或结果存储。

## 3. 验证证据

- 初始 Red：部署契约因 a0v089 部署器不存在而失败；三个未显式开启专用数据库的 PG 用例为 skipped，
  未计作通过。
- 纯分类与部署契约：7 passed、7 个既有依赖 warning，4.19s。
- 显式 `AOS_EXTENSION_PG_TEST=1`、18432 隔离 PostgreSQL：attempt 与 UI-read 35 passed、7 warnings，9.11s。
- 增加数据库无 reason 拒绝及历史 terminal null 兼容后，attempt 专项 16 passed、7 warnings，6.46s。
- saved recovery、schedule worker、UI expired recovery 累计：17 passed、7 warnings，160.27s。
- Python compile、`git diff --check`、Alembic single head 均通过。

## 4. 数据保护与部署器

- 部署器固定 `a0v_088 -> a0v_089`，要求 m1、迁移前导出快照备份、迁移 hash、事务前后读回。
- 数据指纹显式覆盖两张表的全部旧字段，排除新增 nullable schema 字段；因此能证明旧业务值未变，且不会因
  `to_jsonb` 新增 null key 产生伪差异。
- 部署器只改变 schema/trigger；结果声明 `businessWrites=0`、`sourceReads=0`。

## 5. 一致性与风险结论

- 方案要求的受控枚举、同事务 head/event、历史空值、无异常正文、成功空原因、lease expired 固定原因均有
  代码和测试对应。
- 迁移与新应用代码存在顺序约束：必须先迁移 a0v089，再重载 Host；旧 Host 可继续运行旧 schema，不能先加载
  新代码。当前保持旧 Host 与 a0v088 真实库不动。
- 新 reason 只能解释 a0v089 后的新 attempt；不能证明 AM 的 exact failure root cause，也不把测试绿当作自然
  经营闭环完成。

## 6. 下一波

关闭 `lease_renewal.py`、`verification_commit.py`、`preparation_owner.py` 等相邻 Host 续租/时钟闭包；通过后在
无 running attempt 空窗执行 a0v089 备份迁移和 Host 安全重载，再由 Worker 自然产生 AN direct successor。
