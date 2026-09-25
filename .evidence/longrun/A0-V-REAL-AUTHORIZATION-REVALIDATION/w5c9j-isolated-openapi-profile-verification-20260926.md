# W5c9j｜离线 OpenAPI 冷/热计量验证收口

1. 复习 231、W5c9i 和纯 HTTP 零执行边界。
2. 方案先提交 `m1@c2fb21fb`。
3. 静态确认 `app.openapi()` 缓存，不进入 lifespan；实验进程不监听、不查询 DB/商城源。
4. 一次 90 秒有界独立进程完成：import 6.019s、cold 6.241s、warm 0.000001s、2711 paths、5,243,651B，`same_object=true`。未重复运行以美化结果。
5. 无生产代码变化；专项为单次计量/静态复核，无新增逻辑需累计回归。日志含 dotenv 加载和重复 Operation ID/Pydantic 警告，作为风险如实登记。
6. 方案/代码一致性：量级支持冷生成超 5 秒，但非真进程精确时长；不修改启动/超时/缓存策略。
7. 8080 业务浏览器离线，文档计量不算业务验收。
8. audit/verification 精确提交、D-waves/AOS CAS/Prime 更新。
9. 自动 W5c9k：先方案审计重复 Operation ID 的精确路由/文档影响与最小隔离修复可行性；不碰自然 attempt/ACK/closure。

230 L0 挂起、dev-org 零 canary、商城源不读、unknown 不重发/不手工 `run_definition`、m1 单写不 push。
