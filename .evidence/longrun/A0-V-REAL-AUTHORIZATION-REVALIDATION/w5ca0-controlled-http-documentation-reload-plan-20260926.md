# W5ca0｜受控 18181 当前代码加载与只读文档验收

## 上位与现状

复习 231 九步、230 L0 与 W5c9a/e/z：18181 是唯一 m1 精确租约约束的本地 HTTP 诊断进程，不拥有真实业务执行/closure 权限；W5c9n-y 当前代码文档切片尚未加载到旧 PID28077。旧 8080 job 不重启，原 A0-V 十二 Run 未关闭。此波只做 18181 当前代码加载与 `/docs`、`/openapi.json` 只读合同验收，不访问业务 API、不读商城源、不启 Worker/Cron/迁移。

## 精确步骤与门禁

- 新鲜读回 m1 HEAD/dirty scope、唯一 `A0V-W5C9A-HTTP-ONLY-20260926` owner=m1/ACTIVE/18181 scope/未来 expiry，旧 PID28077 的命令必须仍为 `scripts/a0v_w5c9a_http_only_api.py serve`、PPID=1、唯一 127.0.0.1:18181 listener；8080 无监听且旧 launchd API job 缺席；`aos-extension` 仅恢复 PG Up。任何不一致停止，不猜测 PID/重发。
- 运行同 wrapper 的独立 `check --output` 到精确临时 JSON（工具产生、仅白名单读回），确认 outcome GREEN、Host=0、Cron/snapshot/Logic/health/JDBC=false、migration disabled、sourceCalls/runsCreated=0、productionWebIdentityComplete=false；输出不展示身份/凭据。检查失败不动旧进程。
- 仅当以上全绿，给精确 PID 一次 SIGTERM，确认进程退出与端口释放；若结果未知，冻结且不再启动。随后单次 `serve --output`，新 PID 唯一、启动报告同样四零与 0/0、租约守卫存在；不得用过期 lease 重启。
- 只读 HTTP `/docs` 与 `/openapi.json`：先用有界超时并允许一次只读重取（历史冷启动约 6 秒，不是写入），从当前 OpenAPI 检查 10 exact 和 7 shape 后置方法不再展示、paths=2706。若 OpenAPI HTTP 未知仅冻结验收，绝不因它重启或写业务。
- `services/aos-api/aos_api/routers/*` 本波不改；证据只新增本波 audit/verification，D-waves/AOS CAS/Prime 更新。测试复用 W5c9y 29 passed/2 子测试，仅服务读回作为本波专项；8080 业务浏览器仍离线。

## 九步与退出

1. 上位复习；2. 本方案先提交；3. 新鲜进程/租约/零执行前检；4. 精确 stop 与单次 serve；5. 只读 HTTP 专项及既有累计基线核对；6. no-effect 一致性；7. 8080 浏览器离线；8. 证据/上下文；9. 自动下一波。未知提交边界、进程未知或任何零执行 flag 变化立即停止，不在本波重试启动，不扩大到原组 ACK/closure。

230 L0 挂起、dev-org 零 canary、商城源不读、unknown 不重发/不手工 `run_definition`、m1 单写不 push。
