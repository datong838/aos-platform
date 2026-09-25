# W5ca1｜可观察托管启动在预检阶段失败

方案 `m1@0aa7b13a`。新鲜前检：m1/HEAD、18181/8080 无监听、旧 wrapper PID 缺席、恢复 PG 唯一 Up、精确 m1/18181 lease ACTIVE 至 `2026-09-27T04:00:00+08:00`、新 `com.aos.a0v-http-w5ca1` label 与输出路径均不存在。独立交互式 wrapper `check` 明确 `CONTROLLED_API_LOCAL_DIAGNOSTIC_PREFLIGHT_GREEN`，Host=0、Cron/snapshot/Logic/health/JDBC=false、migration disabled、sourceCalls/runsCreated=0、productionWebIdentityComplete=false。

一次 `launchctl submit` 创建专用 label 和 stdout/stderr/preflight 输出。托管进程**已真实进入 wrapper 预检**，但 preflight 为 `STOPPED_FOR_INSPECTION`、`LastExitStatus=256`、18181 无监听。白名单 errorChain 仅含 `FileNotFoundError` 与文件/函数/行号，定位在 `a0v_canonical_ecommerce_first_install.py:439` 的 `subprocess.check_output(["docker", ...])`。交互式 `command -v docker` 为 `/Users/ddt/.docker/bin/docker`，而 `launchctl getenv PATH` 为空；因此“托管环境找不到 docker CLI”是强证据支持的原因，但尚未用新环境实际复测，不宣称唯一可能后续故障。W5ca0 shell 后台命令无进程的原因仍未知，不混同。

本波没有第二次 `submit`，没有读取凭据/商城源，没有启动 API listener/worker/迁移、没有业务请求。失败 label 留作诊断，下一波必须先确认它没有活进程，再精确移除或隔离，给专用新任务设置**仅该子进程**的最小 PATH（不改全局 launchd 环境），新鲜零执行前检后单次可观察启动。若仍失败再次冻结。原十二 Run row proof/Fleet/Owner/ACK/closure no-authority 不变。
