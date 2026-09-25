# W5c9i｜纯 HTTP OpenAPI 首次超时/热缓存诊断

方案 `m1@eb7e86fd`。前检：租约 `A0V-W5C9A-HTTP-ONLY-20260926` 唯一 ACTIVE、m1、只限 `local-process/aos-api-18181`、2026-09-27 04:00 CST 到期；PID28077 唯一监听 127.0.0.1:18181，8080 无监听。已保存预检输出只读选取 flags：Host=0、Cron=false、snapshot=false、migration disabled、sourceCalls=0、runsCreated=0。未打印凭据/DSN、未读商城源。

严格按方案两次 loopback `GET /openapi.json`，响应正文丢弃：第一次 5.006676s 截止，HTTP 000/0 字节（curl 28）；第二次紧接着 0.044676s，HTTP 200/5,243,651 字节。未做第三次 GET、未重启服务、未请求业务路由。静态代码：`main.create_app` 注册十个 domain router，注释记录 505 routers；`ontology_contract_openapi.install_ontology_contract_openapi` 首次经 FastAPI 基础 `openapi()` 生成，再追加 ontology schema，并将结果存入 `application.openapi_schema`，后续直接返回缓存。

分类：**首次生成高于 5 秒、缓存后快速返回，与生成/缓存路径相符**。5 秒客户端超时不证明服务器当刻完成或确切生成时长；第二次快也不能单凭两次请求排除其它并发/调度因素。没有复现稳定每次超时，不据此改生产代码、调高超时掩盖问题或预热 5 MB schema 增加启动负担。本波安全债限定为“冷请求性能未量化”，可在独立隔离进程另波计时，不触碰真实运行进程和租约。`/docs`/OpenAPI 不是 8080 业务浏览器验收。

真实原组 no-authority 不变：12 Run 未闭合、无独立 row proof、Fleet/Owner 全局门缺；不启动 Worker、重发、回填、ACK 或 closure。
