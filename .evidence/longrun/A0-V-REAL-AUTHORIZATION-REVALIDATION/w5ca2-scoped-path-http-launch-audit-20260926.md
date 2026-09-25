# W5ca2｜前检发现旧 label 自动重启，立即停新启动

方案 `m1@0104e49e`。本波计划的“旧失败 label 无 PID”新鲜门禁**失败**：`launchctl list com.aos.a0v-http-w5ca1` 返回 PID35932、LastExitStatus=256，且 `ps` 可见同一 wrapper，18181 无监听。新 label/output 不存在、精确 m1/18181 lease ACTIVE、唯一恢复 PG Up、8080 无监听，但不足以越过旧 label 的活进程风险。依据 fail closed，**没有运行本波 `check`、没有提交带 PATH 的新启动**。

为避免失败 label 继续自动重启，精确 `launchctl remove` 该 label；读回 label/PID/所有 wrapper 进程与 18181/8080 listener 缺席，PG 仍唯一 Up。旧 stdout 有 20 条 `STOPPED_FOR_INSPECTION`，说明 W5ca1 单次 submit 引发了托管器层面的重复预检；原因是 `launchctl submit` 托管语义不能满足本任务的无自动重试约束，不能把它用于 W5ca2 新启动。未访问商城源、未运行原 definition/worker、没有线上 OpenAPI 验收。下一波必须先选择显式无 KeepAlive 的单次托管机制并做隔离负例，然后再谈服务启动。
