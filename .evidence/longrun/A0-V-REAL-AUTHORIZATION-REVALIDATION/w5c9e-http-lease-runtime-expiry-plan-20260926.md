# W5c9e｜18181 专用进程租约到期自停

## 上位边界

承接 W5c9a/d `m1@b239b719`/`c47fb20c` 与 AOS-000692。`A0V-W5C9A-HTTP-ONLY-20260926` 精确 m1/18181 lease 到 2026-09-27 04:00 CST；受控启动器仅启动前验证租约，当前 PID26881 长驻时无法证明到期自停。18181 Host=0/Cron=false/snapshot=false，旧 8080 job 仍 bootout，原组 closure 无授权。本波修**进程所有权**，不升级业务权限，也不新建定时唤醒任务。

## 文件级最小清单

- 只改 `scripts/a0v_w5c9a_http_only_api.py`：在本波专用 `serve` 路径启动进程内租约守卫。读取共享 `leases.json` 的唯一精确 task、owner=m1、ACTIVE、scope=`local-process/aos-api-18181`、timezone-aware expiry；多条/缺失/读错/过期均 fail-closed。守卫定时界限不晚于到期，并对提前撤销每最多 30 秒复核一次；失效向本进程发 SIGTERM，使 Uvicorn 优雅退出。`check` 无守卫，旧 Product/受控 API/其它任务不改。守卫不得打印凭据/lease 全文，不自动续租。
- 新增 `services/aos-api/tests/test_a0v_w5c9a_http_only_api.py`：RED/GREEN 覆盖有效、过期、错误 owner/scope、重复、缺失、坏 JSON、提前撤销与到期触发；信号以注入回调隔离，测试绝不杀自身或碰真实 18181。
- 专项和相关累计通过后，精确确认当前 PID26881/18181/Host0/唯一 PG，发送一次 SIGTERM 停旧**专用 HTTP**进程，读回端口释放；单次以新 wrapper 重启并验证同一零执行 flags/PID、租约守卫已启动。若 PID 不一致/未知 listener/停机结果未知，STOP，不杀广泛进程。
- 真库/Worker/原 Run 不读写；浏览器业务 8080 离线不填 GREEN。

## 九步

1. 复习 W5c9a/d、租约治理、Uvicorn 退出路径及当前现场。
2. 本方案先提交。
3. 新鲜 PID/租约/端口/PG 前检；单元 RED。
4. 本波 wrapper 最小守卫，旧代码行为不变。
5. 专项 GREEN、相关累计；负例 fail-closed。
6. 精确受控重载 18181 并即时/有界读回零执行与守卫；无重发。
7. 8080 业务浏览器仍离线；方案/代码与安全边界复审。
8. audit/verification、m1、D-waves/AOS CAS/Prime。
9. 自动下一波：继续独立 Fleet/Owner 权威合同或其它安全债；原组关闭保持冻结。

230 L0 挂起、dev-org 零 canary、unknown 不重发/不手工 run_definition、m1 单写不 push、不读商城源。
