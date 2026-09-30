# BG00ET verification — 2026-10-01

## RED → GREEN
- Missing entry: session91040, 9 failed/66.45s/exit1;真实子进程缺模块，并暴露包初始化载入整个Web应用。
- Import regression RED: session87200, 1 failed/11.98s/exit1，断言 aos_api.main 不应出现在独立包导入后。
- 最小实现后专项 session60966：11 passed/6.39s/exit0。
- 最终累计 session5238：74 passed/24.41s/exit0，7项已有warning。

```sh
services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_network_consumer_cli.py services/aos-api/tests/aip/test_network_consumer_config.py services/aos-api/tests/aip/test_network_consumer_process.py services/aos-api/tests/aip/test_network_consumer_connection_pg.py services/aos-api/tests/aip/test_network_consumer_signed_https_pg.py services/aos-api/tests/test_health.py services/aos-api/tests/test_logging.py --tb=short --show-capture=no
```

## 复审
显式check/serve必填；无默认启动，禁止重复/缩写/未知参数并固定错误码。读取私有配置后强制readonly preflight，再调用有限进程；无内部重试。typed预检scope不是请求授权，每条IPC仍独立JWT/actor/tenant/approval。serve统计不是业务结果。包仅按需导出历史app/create_app，真实子进程导入CLI及config不加载main；历史导出对象兼容，健康/就绪与日志回归通过。

真实子进程+隔离PG完成check、serve空闲退出、Receipt无新增、socket清理、占用路径保留；测试OS配置不代表正式独立账号验收。无页面改动，browser验收不适用。git diff --check退出0。

## 未完成与下一波
正式OS账号/组/扩展ACL、IdP、签名配置来源以及当前部署尚未核验；本波没有操作当前真实库，没有部署119–122或启Host/worker/Provider，不读商城源/旧Run、不手工run_definition、不push。a0v_118为上一波真实库基线，本波未刷新。
BG00EU应回到正式部署材料的只读盘点，列出缺失authority与产品接线，优先首链必要项，不以继续增加孤立测试代替正式接入。
