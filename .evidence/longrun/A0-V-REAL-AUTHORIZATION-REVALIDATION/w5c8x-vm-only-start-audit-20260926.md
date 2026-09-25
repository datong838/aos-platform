# W5c8x｜真实 profile 仅 VM 启动运行态审计

方案 `m1@a1f9314b`。前检：m1；真实 `aos-extension=Stopped`、独立测试 VM Running；8080/18181 无监听、8080 launchd job 不在表；测试 VM `losetup -l` 空且无 W5c8 残留挂载。停止 profile 的 Docker socket 不存在属预期，不以其失败重试状态变更。

2026-09-26 03:22:21 CST 唯一一次 `colima start -p aos-extension`，约 9 秒退出码 0，启动输出 `done`。未执行 `docker start`、migration、应用 bootstrap、DB 查询或 Run/商城源读取。

紧随回读：`colima list` 显示真实 profile Running；`docker --context colima-aos-extension ps` **0 个运行容器**；8080/18181/18435 均无监听，8080 launchd job 仍缺席。`docker ps -a` 的三个原 PG 容器均 `Exited (255)`、restart=`no`。`docker inspect` 白名单显示其 `StartedAt` 分别为 2026-09-20、09-22、09-24 的历史时间，没有本次新 start；`FinishedAt` 均更新为 2026-09-25 19:22:29Z，即 Docker daemon 在本次启动时重建退出态，不能只看 ps-a 的“16 seconds ago”就宣称容器新运行。未读取 Env、Mount、Logs 或卷内容。

已证仅为 VM-only 起点；真实 PG 仍 stopped，原 12 Run/Receipt 未读，8080 API 继续离线。宿主其他 AOS job 的潜在影响与后续 DB 启动门仍需单独证明。若后来发现意外容器/端口，冻结，不重发 attempt。
