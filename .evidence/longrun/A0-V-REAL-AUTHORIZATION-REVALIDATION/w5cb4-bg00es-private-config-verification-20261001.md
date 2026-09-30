# BG00ES verification — 2026-10-01

## 实现和方案复审
私有 JSON exact schema、16 KiB 限制、0700/0600、euid owner、O_NOFOLLOW/dir_fd、读取前后 fstat；复用数据库和进程配置类型。O_NONBLOCK 防止 FIFO 在 fstat 前阻塞，真实 FIFO 负例覆盖。预检仅只读连接，复用 120/121/122 SQL 函数身份/ACL 门；显式 businessAuthorized=false。缺少 typed TenantScope 拒绝。

## 验证
原始 RED：模块缺失，pytest 收集退出 2（原 session 35947）。初始实现 11 passed/4.31s。原累计进程 64935 回读：59 passed/16.18s/exit 0。复审补齐方案指定的未类型化 scope 负例后：

```sh
services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_network_consumer_config.py services/aos-api/tests/aip/test_network_consumer_process.py services/aos-api/tests/aip/test_network_consumer_connection_pg.py services/aos-api/tests/aip/test_network_consumer_signed_https_pg.py --tb=short --show-capture=no
```

session 70192：60 passed，7 existing warnings，16.39s，exit 0。真实隔离 PG 与临时 TLS/JWT；不是正式 IdP/独立 OS 账号验收。真实预检前后 Receipt 数相同，无 socket、无新增 attempt 文件。无 UI 修改，浏览器不适用。

## 风险与边界
权限位检查不构成扩展 ACL、祖先目录全链和正式安装来源的完整证明；部署仍须核验。ready 只代表所查配置/连接/函数门，不是业务授权。当前正式库沿用上一波 a0v_118 事实，本波未查询或迁移；代码 119–122 未部署。Host/worker/Provider 未启动。首链未完成。无商城源读取、旧 Run 重放、manual run_definition 或 push。

## 下一波
BG00ET：有界消费者入口组合，私有配置→只读预检→有限生命周期；先方案与入口负例，保留正式授权边界。
