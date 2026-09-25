# W5c9i｜18181 纯 HTTP OpenAPI 有界诊断方案

## 上位与目的

承接 W5c9h `m1@9d798781`、AOS-000696：原十二 Run 的独立行级语义证明与 Fleet/Owner/closure 权威仍缺，禁止借本波做历史回填/ACK/重发。W5c9a 首次 `/openapi.json` 5 秒超时，`/docs` 200 仅说明 HTTP 文档壳可达；这是可独立处理的纯 HTTP 可观测性债，不以真实商城源或自然 Worker 为前提。

## 文件级范围和边界

- 只读检查 `scripts/a0v_w5c9a_http_only_api.py`、`scripts/a0v_controlled_api.py`、API 启动与 OpenAPI 路由构建；不打印 env/DSN/凭据。
- 确认唯一 18181 listener/精确租约、8080 无 listener、Host=0/Cron=false/snapshot=false/migration disabled，才对 `/openapi.json` 最多 **两次** loopback GET：第一次 5 秒上限，第二次 30 秒上限。任何不明响应/配置漂移即停，不重启服务或触发业务路由。
- 若可复现超时，基于本地静态 profiling/隔离测试寻最小修复；改代码前补本方案细化/另立方案，先 RED 后 GREEN。若仅冷生成耗时，记录实际耗时与体量，不通过调高上限掩盖持续故障。
- 证据限定状态码、耗时、响应字节数、进程/端口、代码调用链；不存 API schema 全文或敏感参数。业务浏览器 8080 离线，不能宣称业务验收。

## 九步

1. 复习 231、W5c9a/e/h 与租约/零执行边界。
2. 本计划先提交，再前检与有界 GET。
3. 静态定位建模/构建路径并记录可重现条件。
4. 如需修改，先方案补订和文件级清单，最小代码及专项负例；否则 no-code 诊断收口。
5. 累计相关测试只在受影响范围运行，不借旧结果冒充。
6. 方案/代码一致性、安全和未知边界复审。
7. 8080 业务浏览器离线，18181 仅纯 HTTP 技术检查。
8. audit/verification、精确 m1 提交、D-waves/AOS CAS/Prime 更新。
9. 自动下一波：依据真实诊断挑独立安全债；原组 ACK/closure 冻结。

m1 单写不 push、不动其他分支；230 L0 挂起、dev-org 零 canary、商城源不读、unknown 不重发/不手工 `run_definition`。
