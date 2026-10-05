# 独立当前142迁移零窗口审计

Task w5cb4-current142-zero-window-audit-20261005，仅只读审计与方案，无服务控制/当前DDL权。前门代码5183ed2d完整隔离恢复成立，不能替代正式当前迁移。09:38实际当前库其他连接0，但只是一刻快照，不能证明持续零执行窗口。8080 PID67821及8434 PID67820仍监听。下一完整核对父进程/原启动路径/Host-worker-Provider及全部可达写者，形成唯一停止/恢复路径与正式窗口锁定证据；在独立正式Task和停写后新全备再完整恢复之前禁止当前DDL。迁移失败保留资料，不回放业务、不自动downgrade数据或删除卷。服务重启须签名/build与最新HEAD/schema一致，实际PG→API→Web及浏览器验证，不以200作自然首链。

本阶段实际源库读操作无query文本输出、无秘密；没有停止服务。com.prime-agent.daemon标签查无结果仅说明该猜测标签不存在，下一按实际LaunchAgent查证，不称Prime已停止。

## 实际控制归属与窗口设计补正

最新audit.json：当前135，其他连接0/预备事务0；本审计transaction_read_only=on，但服务器default_transaction_read_only=off。故“当前只读”是本thread操作约束及审计连接实际只读，不能宣称数据库强制只读。唯一LOGIN且CONNECT角色为aos_app超级用户；不可用普通REVOKE CONNECT或默认只读GUC证明owner不可写，亦不可用0连接快照证明下一刻无写者。

实际8080/8434启动于00:49:12，两个shell父进程→WorkBuddy sandbox PID64915；三个候选LaunchAgent均未注册，旧api8080 plist格式无效、daily/web候选有效且KeepAlive/RunAtLoad。禁止按未注册标签盲停/重启或加载重复实例；禁止把格式问题当服务已停止。Prime实际com.aos.prime-agent-safe PID1844/LastExitStatus0，仅服务回读，不外推模型质量。

下一正式门必须先制定受控维护窗口：仅停止精确核验的API/Web两个叶进程，不kill父WorkBuddy或其他用户进程；阻止候选恢复器重拉及并发入口，固定当前DB/卷身份。单靠业务表锁、advisory锁、默认只读或CONNECT REVOKE均不足以对未配合superuser保证零执行；须在维护数据库连接上实施可回读的数据库连接禁入/已有连接排空策略，并安排容器本地受控迁移通道与完整故障恢复演练。禁止本审计Task执行ALTER DATABASE/ROLE/连接终止/服务停止。先隔离实测该窗口机制、拒绝新连接与迁移通道完整恢复，再另开当前正式Task；原业务数据不改，旧卷/备份全保留。不将“当前库迁移缺窗口”扩大成全部安全工作停止，b90完整evaluator计划仍可推进。
