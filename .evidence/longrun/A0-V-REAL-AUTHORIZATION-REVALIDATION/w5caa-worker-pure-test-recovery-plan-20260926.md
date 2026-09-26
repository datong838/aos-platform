# W5caa｜W5c8h Worker 10 项环境错误的纯测试重验方案

## 上位与历史边界

复习 231 A0-V→A1、230 L0、W5c8h 当时 10 项在 session PG 夹具连接 5433 前 setup ERROR、W5c8i 旧 unknown 入口隔离撤权、W5ca9 专用 PG 负例。`test_analysis_data_requirement_worker.py` 的十项用例主体均用 stub/monkeypatch，不应为了纯逻辑测试启用 PG/真实 Host；W5c8h 的错误是环境事实，不是代码通过或失败。

## 文件级与验收

- 只读：`services/aos-api/tests/extension_runtime/test_analysis_data_requirement_worker.py`、`services/aos-api/tests/conftest.py`、W5c8h/i verification、当前 m1/AOS-000724。
- 优先以项目 `.venv`、`AOS_DOTENV_DISABLED=1`、`pytest --noconftest` 只运行这一个纯测试文件，明确 10 项正式结果；不得设置 `AOS_TEST_USE_SHARED_DATABASE=1`。如果用例实际依赖数据库或触发业务服务，停止并补单独隔离方案；本波默认不改生产代码。
- 如测试暴露确定性缺陷，先写文件级修订再最小修复；若 GREEN，仅补本目录 audit/verification、D-waves/AOS 上下文与 Prime，删除对应过时的 setup-only 当前风险。无真实数据库、Host、8080、18181 或源读写。
- `py_compile`/diff check，确认 18181 原进程、8080 离线；业务浏览器不可验收。

## 九步

1. 上位复习；2. 本计划先提交；3. 纯文件与夹具静态审；4. 最小测试重验/必要修复；5. 专项/短累计；6. 业务浏览器离线如实记录；7. 方案/实际测试范围复审；8. verification、AOS/Prime、提交；9. 自动下一波。

真实 `a0v_096–098` 未部署、旧 unknown 执行旁路在真库可能尚存；Worker 测试 GREEN 不授权原组对账/ACK/closure，unknown 不重发、不手工 run_definition；230 L0、商城源不读、dev-org 零 canary、m1 单写不 push。
