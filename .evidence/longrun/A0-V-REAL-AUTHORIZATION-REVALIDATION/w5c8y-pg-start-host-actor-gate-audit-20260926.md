# W5c8y｜PG 启动前宿主 actor 与 HTTP 零执行静态审计

方案 `m1@20a35e6a`。真实 VM Running、`docker --context colima-aos-extension ps` 0；三个原 PG 容器 exited；8080/18181/18435 无监听，8080 launchd job 缺席。本波未启动任何容器/服务，未读数据库或商城源。

宿主 AOS launchd 仅 `com.aos.a0v-web-8434` 与 `com.aos.prime-agent-safe` 有 PID；其它 memory-health/watchdog/ollama job 当前无 PID。对应 plist 仅提取 Label、RunAtLoad/KeepAlive、可执行 basename 与白名单布尔：旧 8080 API 有 7 个 AOS/DB/worker 相关环境键且 KeepAlive=true，仍不安全；Web node、Prime safe shell、其它当前作业均未见相关环境键、直接 postgres/18435/database/run_definition 参数或 worker 参数。Prime safe 当前 `lsof -iTCP` 无连接；其 86 行启动脚本关键词扫描未见 AOS API/Postgres/psql/Docker/Colima/curl/uvicorn/database/db_/worker，只有通用 runtime 字样。未输出 plist Env 值、完整 ProgramArguments、DSN 或脚本原文。

纯 HTTP 启动器 `scripts/a0v_product_controlled_api.py` 与 `services/aos-api/tests/test_a0v_controlled_api.py` 静态契约包含 Host=0、Cron=false、snapshot worker=false、migration disabled；本波针对该测试文件实跑 `13 passed`、7 个既有 warning。它仅证明代码契约，不等于真实 18181 运行态。宿主间接行为不能由参数/关键词完全排除，故本波只为下波“唯一 PG 容器+即时回读”提供候选，不授权旧 8080 job、Worker、迁移或 ACK。
