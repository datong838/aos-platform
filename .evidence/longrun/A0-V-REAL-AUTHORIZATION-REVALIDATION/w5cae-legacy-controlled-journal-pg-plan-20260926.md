# W5cae｜旧 Controlled Journal 18432 隔离回归补跑方案

## 上位与当前证据

231 A0-V→A1、231-9 BG-00 未变；W5cad 在 5433 隔离关闭夹具和邻近回归中得到 9 passed、16 skipped。16 项来自 `test_lifecycle_pg.py` 明确 `AOS_EXTENSION_PG_TEST=1` 门，固定连接 `127.0.0.1:18432` 的旧 AR1-c 专用 PostgreSQL，不是本次 5433 测试库。`aos-ar1c-pg` 当前 Exited、无 Mounts、RestartPolicy=no；其端口不是 18435 恢复真库。`pytest --collect-only` 两文件当前正好 16 项。

## 文件级/资源清单

- 只读运行 `services/aos-api/tests/extension_runtime/test_pipeline_controlled_ingress_journal_pg.py` 与 `test_pipeline_completed_input_pg.py`，连同其 `test_lifecycle_pg.py` 专用 fixture；不改生产或测试代码。
- 只对现有 `colima-aos-extension` 中已停止的 `aos-ar1c-pg` 作临时 start/stop。启动后核验仅 127.0.0.1:18432；使用项目 `.venv`、`AOS_DOTENV_DISABLED=1`、`AOS_EXTENSION_PG_TEST=1`，且不设置 `AOS_DATABASE_URL`，在 600 秒单调有界 runner 内唯一运行。结束把该容器停回 Exited；不删除容器、不动 18435 真库。
- 本目录 verification 与必要 AOS 项目开发上下文/Prime 受管记忆。用户其他未跟踪/脏文件一律保留。

## 九步/退出与停止

1. 复习上位、fixture 端口/角色门与 W5cad 跳过事实。2. 本方案先落盘提交。3. 核验 18432 无 listener、容器原状态，精确启动已有 test-only 容器。4. 单次有界 16 项运行；失败/超时按实际结果记录，不盲目重试。5. 核验 fixture 资源清理与专项结果，再停回容器并读回状态/端口。6. 18181 浏览器只读文档可用性复核，8080 业务浏览器不可验收。7. 方案/测试/真实授权边界复审。8. verification 落盘提交，CAS/Prime/共享上下文同步读回。9. 自动下一波回外部门禁与其他安全技术债。

该旧夹具以命名 fake asset authority 及专用数据库为前提，即使 16 项 GREEN，也只证明旧 Journal/CompletedInput 代码路径，不证明真实 Fleet、Owner、原 12 Run、商城数据或业务接受；230 L0 继续挂起、dev-org 仅隔离 canary、m1 单写不 push。
