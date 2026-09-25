# W5c9z｜剩余 OpenAPI 可达性与受控部署门禁只读复盘

## 上位/目标

复习 231 业务闭环九步与 230 L0 真实权限边界、W5c9l/m/u/w/x/y 的冲突/匹配/文档证据。此前明确的十组 exact 与七组 shape 只完成文档去重，并未加载到 18181；8080 离线。不得将代码 GREEN 转为线上 GREEN 或启动原 A0-V worker。目标是读出“下一次可安全推进什么”，不以消警告为由扩展代码范围。

## 文件级只读清单

- `services/aos-api/aos_api/main.py`、domain router manifest、当前 FastAPI `iter_route_contexts`：无 lifespan 的单进程核查十组 exact、七组 shape 的代表 matcher/`include_in_schema`/OpenAPI 可见性；统计尚存 exact 重复 operation 与 shape 双文档，不读取业务数据，不调用任何 handler。
- `.evidence/.../w5c9e*` 受控 18181 租约/启动与 W5c9i/j 冷启动证据：只读检查进程、端口、lease 过期时刻和当前部署前置，禁止打印环境变量/密钥、重启、迁移或触发 Cron/worker。
- 审计/verification 文件落盘；如发现剩余冲突，下一波先精确设计；如文档冲突消除但线上部署仍需 Host/Owner/lease 等权威，单列部署门禁，不自行放开。D-waves/AOS CAS/Prime 收口。

## 九步

1. 上位复习；2. 本方案先提交；3. 静态清单；4. 一次 bounded no-lifespan 审计；5. 无代码专项/累计，复用 W5c9y 29 passed 基线而不冒充本波测试；6. 方案/状态复审；7. 浏览器离线；8. 证据与上下文；9. 自动下一波。

230 L0 挂起、dev-org 零 canary、商城源不读、unknown 不重发/不手工 `run_definition`、m1 单写不 push。
