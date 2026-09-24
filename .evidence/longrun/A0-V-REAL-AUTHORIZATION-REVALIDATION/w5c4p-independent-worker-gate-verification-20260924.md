# W5c4p 独立 snapshot worker 启用前门禁验证（2026-09-24）

方案 `2420e9d3`，补充 `6745d330`/`7d6e6ef8`/`91504eb9` 先于代码修改。未 enable definition、未手工 Run、未读商城源行。

- 初始只读：18181 无监听；旧 BL 状态 2026-09-20 STOPPED/PID63195，旧 BL 与底层受控 API lease 均已过期；Host PID17302、8080 PID31967 存活。正式 `memory-receipt task-start` 以 authority `AOS-000574` 新建专用 `A0V-W5C4P-SNAPSHOT-WORKER-20260924`，owner m1、scope 仅 `local-process/aos-api-18181`、有效至 2026-09-25 12:00 CST；旧 task 未复活。
- 新 wrapper `scripts/a0v_w5c4p_snapshot_product_api.py` 只覆写当前 private identity/bundle/trust 路径、独立状态路径和本波 lease；`scripts/a0v_controlled_api.py` 仅允许旧默认或本波白名单 lease，校验 m1/有效期/18181 精确 scope；基类 `scripts/a0v_snapshot_product_api.py` 历史默认保持不变，并对本波 task 再核 scope。第一次 `check` 因旧默认凭据路径 `HostBlocked` 且无进程副作用；方案补充后以当前 Host 精确私有路径重检通过，诊断 preflight 显示 Cron=false、migration=false/disabled、Host in API=false、snapshot worker=true/independent、sourceCalls0/runsCreated0。
- 08:41 UTC 唯一 `serve` 启动，18181 唯一 listener PID37241；08:41–08:42 UTC 私有 status `IDLE`、`workerTaskAlive=true`、`workerError=null`、`hostInThisProcess=false`、`topology=independent`。18181/8080 `/openapi.json` 均 HTTP 200，Host PID17302 与 8080 PID31967 未变。新定义 W5c4o 独立只读 audit 仍 `W5C4O_DISABLED_DEFINITION_REV2_GREEN`，12 schedule off。
- `py_compile`、定向测试 **16 passed**、`git diff --check` 通过。测试覆盖新 lease 的正确 scope、错误 scope、过期、任意 task 拒绝，以及 worker lease/第二实例锁；现行 HTTP/进程状态是活体验证，不将其视为业务执行成功。

下一波 W5c4q：在启用前再次实时核定义 rev2、12 最新链、24 小时窗口与预算 rev13 对下次 20:00 UTC slot 和有界执行的覆盖、18181/Host 单例与三 held、九路/claim gate、无在途/canary。任何一项未知保持 disabled；全绿才用新 key/精确 expectedRef 正式 enable，并持续只读监督自然 slot，不手工 `run_definition`。
