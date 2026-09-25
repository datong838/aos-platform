# W5c6o JDBC 退出清理日志生命周期方案（2026-09-25）

上位：D2.6 JDBC 通用运行时要求退出释放连接/SSH 隧道、失败不静默；AR1-c 多波证据一直记录 pytest 结束后 atexit 向已关闭 capture stream 写日志的既有噪声。A0-V W5c6n 复现 exit 0 后 `ValueError: I/O operation on closed file`。本波只修日志通道生命周期，不改变清理次序、异常吞吐或任何 A0-V 权限/效果。

## 文件级九步

1. 复习 D2.6 运行时头部合同、`_cleanup_all_cached`/FastAPI shutdown/atexit 双入口、原 `services/aos-api/tests/test_jdbc_connector_runtime.py`。
2. 本方案先提交；候选最小文件 `services/aos-api/aos_api/jdbc_connector_runtime.py` 与 `services/aos-api/tests/test_jdbc_connector_runtime.py`，加 verification。若不能证明连接/隧道释放不变则停在 no-effect 诊断。
3. 测试先证实 atexit 清理在无活缓存时仍写日志、已关闭 capture handler 可致 stderr 错误；shutdown 正常调用仍需留原诊断。
4. 仅把 atexit 入口改为静默日志的同一个清理函数；连接和隧道 close/clear 完全沿用，关闭异常仍不阻止后续资源清理。正常 FastAPI shutdown 保留日志。静默仅适用于解释器退出、日志系统可能已拆卸的窗口。
5. 专项测试及 W5c5k–W5c6m 累计回归；子进程 pytest 输出不含 closed stream traceback，不能只看 exit 0。
6. 浏览器只读 A0-V rev4 disabled，不保存/运行/冲刷队列；本波无 UI 变更，验收为防漂移。
7. 复审清理语义、日志可观察性与方案一致性，不扩大为日志框架重构。
8. verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立记忆并读回。
9. 下一波检查旧 Schedule 长时组合回归可验证性及余下测试债，仍先方案后实现。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 仅零 canary。
