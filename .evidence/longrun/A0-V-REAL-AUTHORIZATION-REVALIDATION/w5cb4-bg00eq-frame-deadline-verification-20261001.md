# BG00EQ 整帧截止时间验证

基线AOS-001005/m1@e5060ee7。实际Unix socket每1秒发1字节，header4+body3总7秒，原实现未拒绝：句柄17104，1 failed/2 passed/11.05s/exit1。测试不替换时钟或recv；验证失败后Event停止sender并join，无遗留线程。

共享read_issuer_frame最小修改：monotonic+5秒同一deadline覆盖header/body，每次recv设剩余timeout，完成后复检，finally恢复原timeout。帧长/身份/错误脱敏/业务分派不变；consumer直接复用，因此两入口均覆盖。

```sh
services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_network_ipc_deadline.py services/aos-api/tests/aip/test_aip_network_issuer_ipc.py services/aos-api/tests/aip/test_network_consumer_ipc.py services/aos-api/tests/aip/test_network_consumer_signed_https_pg.py services/aos-api/tests/aip/test_network_consumer_service_pg.py --tb=short --show-capture=no
```
句柄87313：**47 passed/22.45s/exit0**。慢速真实socket约5秒拒绝（测试4.5–6.5秒容差），原12秒timeout恢复；正常与截断恢复通过，issuer/consumer IPC及HTTPS/PG消费相邻保持通过。git diff --check exit0。

复审：只改共享读取函数，使用单调时钟避免墙钟跳变；未延长任何等待预算。超时响应仍脱敏，不引发消费重试。本波不需要浏览器（无UI变化），未触当前真实库/Host/worker/Provider，不push。旧登录403基线债与正式跨UID/外部身份、当前部署/首链仍未完成，不因本波47测试消失。

下一波BG00ER回消费者进程生命周期：当前只有open/serve_one函数，无受控入口组合；先方案确定配置来源与有限接收/退出清理、不越过OS/身份门，再RED/最小实现。当前118库到代码122部署独立备份/克隆/零窗口，230 L0挂起。
