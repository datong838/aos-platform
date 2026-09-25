# W5c8x｜VM-only start 验证收口

1. 复习 W5c8v/w、AT/AS 及 AOS-000685；真实 VM 停止、8080 bootout。
2. 方案先提交 `m1@a1f9314b`。
3. 新鲜前检成立：profile/端口/launchd/loop/mount 符合预期。
4. 单次 `colima start -p aos-extension` 成功；没有任何 Docker/DB/worker 启动命令。
5. 即时专项读回：真实 VM Running，`docker ps` 0、8080/18181/18435 无监听、8080 job 缺席；三个原 PG 容器 exited 且 restart=no，StartedAt 均旧。无代码变更，不把既有 82 tests 冒充本波测试。
6. 业务浏览器验收因 8080 API 离线不能执行，不填 GREEN。
7. 方案/现场一致：只证 VM-only，不证真库/原 12 Run closure；`FinishedAt` 更新仅为 daemon 状态恢复，不能当新 attempt。
8. audit/verification 精确提交、D-waves/AOS CAS/Prime 更新。
9. 自动 W5c8y：先方案，再只启动**唯一**原 PG 容器并进行无执行 HTTP 配置门；启动 DB 前必须再验 8080 job/Host/worker 防线。任何偏差冻结，不能手工 run_definition 或重发。

230 L0 挂起、dev-org 零 canary、m1 单写不 push、不读商城源数据。真实 profile 现保持 Running，但 PG 容器均 stopped；旧 8080 job 绝不 bootstrap。
