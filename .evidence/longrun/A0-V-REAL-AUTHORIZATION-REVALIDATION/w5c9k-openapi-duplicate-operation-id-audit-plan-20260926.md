# W5c9k｜OpenAPI 重复 Operation ID 精确影响审计方案

## 继承门禁

W5c9j `m1@41c22e2f`/AOS-000698 在离线 schema 生成看见重复 Operation ID 警告；这只是文档契约线索，不能外推路由调用错误。18181 零执行、8080 离线；原组 12 Run row proof/Fleet/Owner/ACK/closure no-authority 保持。

## 文件级清单

- 静态读 `services/aos-api/aos_api/main.py`、`routers/domain_aggregates.py` 与警告指向的 `routers/phase5_schedules.py`/`phase5_datasets.py`，确认是否重复挂载或仅名称重复。
- 一次短命无 lifespan/无端口/无源进程生成 schema，对所有 path+method 的 operationId 分组；只输出冲突组数量及方法/路径/ID，不输出 schema/敏感请求字段。90 秒上限；同一运行同时统计 path+method 重复、路由表对应数量。未知或超时不重发。
- 如果只是 OpenAPI 命名冲突且范围可控，本波只出审计/verification，下一波先方案再做最小修复；若实际路径/方法遮蔽，冻结修改直到明确兼容风险。不得更动真实运行进程、DB 或 API 路由行为。

## 九步

1. 复习 231/W5c9j/零执行边界。
2. 本方案先提交，复查 exact m1/租约/18181。
3. 静态源路径审计。
4. 一次隔离 schema 聚合，不打印全文。
5. 无代码时专项为确定性聚合，累计回归不冒充。
6. 方案/代码/兼容风险复审。
7. 8080 业务浏览器离线。
8. audit/verification、精确提交、D-waves/AOS CAS/Prime。
9. 自动下一波处理已定位的最小修复方案或其它独立安全债。

230 L0 挂起、dev-org 零 canary、商城源不读、unknown 不重发/不手工 `run_definition`、m1 单写不 push。
