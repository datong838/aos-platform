# 基础批次回执只读核验验证

2026-09-11，基线2a4f2f7b。read_committed_batch重新验证原命令，复用已有scope/idempotency筛选及hash匹配；缺失返回None，冲突沿既有错误码，返回原BatchResult不标记成新执行。提交路径仍默认FOR UPDATE，只读路径无行写锁。

新用例先红后绿，既有SQLite一致性内核全31项通过；缺失、提交后读回、只变CAS guard可读、实际内容变化拒绝，读取前后Receipt/Outbox行及checkpoint一致。diff --check通过。既有7警告与退出日志问题仍在。

不是PG权限/RLS或真实源实测；有回执也可能含ignored/dangling结果，消费端不能当作全业务成功。下一步恢复服务组合原命令、已提交回执与派生journal，尚未实际开启续跑。API未重载、完整经营首链未完成，不push，230 L0挂起。
