# W5ca7｜HTTP-only 租约守卫隔离进程退出补证方案

## 上位与现场

复习 231 A0-V→A1 串行、230 L0 挂起、W5ca3 18181 显式 `KeepAlive=false` 与 W5ca5/6 原组 no-authority。W5c9a 的 `watch_lease` 已有纯函数、假时钟/假 Event、启动接线单测，但真实 2026-09-27 04:00 CST 租约到期尚未发生，不能称 live 自停。W5c9f 已独立完成恶意自洽见证测试，本波不得重复。

## 文件级最小变更

- 只读复习 `scripts/a0v_w5c9a_http_only_api.py`、`services/aos-api/tests/test_a0v_w5c9a_http_only_api.py`、W5ca3/W5c9a verification。
- 只改 `services/aos-api/tests/test_a0v_w5c9a_http_only_api.py`：临时租约文件 + 独立 Python 子进程，替换 `load_launcher` 为只等待的无端口假启动器；验证 `serve` 守卫在短时到期和文件状态撤销后，子进程以 SIGTERM 退出。无真实 credentials/PG/HTTP/商城源调用。若现有守卫存在缺陷，再另补方案审生产最小修复，不能在本方案中顺手改。
- 专项 `pytest --noconftest`；邻接运行同一测试文件；超时必须精确终止测试子进程并收集诊断，不碰 18181 PID。测试后无残留测试子进程、无临时租约。
- 本目录 audit/verification、D-waves、AOS/Prime 记忆与精确 m1 提交。

## 九步与验收

1. 复习上位/现有守卫；2. 本计划先提交；3. 子进程专项 RED；4. 最小测试或必要时先补生产修订方案；5. 专项/邻接回归；6. 8080 离线，18181 `/docs` 仅文档只读，不当业务浏览器验收；7. 方案/测试/运行副作用复审；8. verification、上下文/Prime、提交；9. 自动下一波。

隔离子进程 GREEN 只证明受控终止机制，不证明真实租约到期现场或全机 Fleet。原十二 Run、ACK/closure/源读取、230 L0、dev-org 零 canary、不 push 均不变。任何未知子进程结果先定位/清理该测试 PID，不重跑真实服务。
