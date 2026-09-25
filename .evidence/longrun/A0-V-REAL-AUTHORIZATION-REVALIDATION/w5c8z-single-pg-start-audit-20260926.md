# W5c8z｜唯一恢复 PG 容器启动审计

方案 `m1@4e1fa83c`。前检：真实 `aos-extension` VM Running、真实 context `docker ps` 0；目标 `aos-a0v-recovery-pg` 的 image=`postgres:16-alpine`、restart=`no`、端口仅 `127.0.0.1:18435->5432`、state=exited；另两个 PG exited；8080/18181/18435 free、8080 launchd job 缺席。

仅一次 `docker --context colima-aos-extension start aos-a0v-recovery-pg` 退出码 0，回显目标名。即时 `docker ps` 只有该目标 Up，另外两个 PG 仍 Exited；18435 的监听为本机 127.0.0.1 SSH 转发，8080/18181 无监听，8080 job 仍缺席。容器内 `pg_isready -h 127.0.0.1 -p 5432` 回显 accepting connections。未登录数据库、查询任何业务表、读取商城源、运行迁移、启动 API/Worker 或手工触发 attempt。

已证仅一个 PG 服务可达，不等于原 12 Run/Receipt closure 或纯 HTTP profile 安全运行。原 8080 plist 仍不安全，绝不 bootstrap；下一波须按 AT 方案启动受控 18181 并实测 Cron=false、snapshot=false、Host=0、迁移 disabled 的运行态，且先确认不会对本库自动迁移/执行。
