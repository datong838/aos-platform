# W5ca7｜HTTP-only 租约守卫隔离进程退出 verification

1. 上位：231 A0-V→A1、230 L0 挂起、W5ca3 18181 无 KeepAlive、W5ca5/6 原组 no-authority 已复习；W5c9f 恶意自洽见证测试已完成，未重复。
2. 方案 `m1@54e0776f` 先提交；最小代码目录 `services/aos-api/tests/`，仅扩 `test_a0v_w5c9a_http_only_api.py`，生产守卫/启动器/租约文件均未改。
3. 首次 `python3 -m pytest --noconftest` 由于系统 Python 不支持脚本的 `datetime | None`，11 个用例均在 setup 导入时失败，未执行逻辑；按项目 `.venv` 重跑，不把该次记为逻辑 RED。
4. 子进程使用 `tmp_path` 临时租约与无端口等待式假启动器，不读取凭据/PG/商城源；真实 watcher 线程和 `os.kill(SIGTERM)` 在到期和状态撤销两种情形下均使测试子进程退出。无生产改动。
5. 项目环境专项 `11 passed in 35.15s`；轻微诊断断言清理后最终专项 `11 passed in 35.16s`。邻接 `test_a0v_w5c9d_reboot_safe_host_diagnostic.py` 累计 `17 passed, 6 warnings in 43.01s`；警告为现存模型字段 shadow。测试子进程已无残留；现场只剩原 18181 PID36529。
6. 8080 无业务 listener，浏览器业务验收不适用；18181 唯一 loopback listener PID36529、`/docs` HTTP200 仅文档探针，不发送业务请求。
7. 本波只证明**隔离进程**租约终止机制；真实 2026-09-27 04:00 CST 到期自停尚未发生，全机 Fleet/Owner/历史行门未被补齐。
8. 本文件、D-waves、AOS/Prime 独立记忆和 m1 精确提交后读回；不 push。
9. 下一波继续独立可证的安全债；原组十二 Run/ACK/closure、源读取、230 L0 持续 no-authority，不能因此进入 A1。
