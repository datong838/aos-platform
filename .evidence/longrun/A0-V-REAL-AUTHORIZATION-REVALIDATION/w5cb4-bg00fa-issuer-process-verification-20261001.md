# BG00FA verification — 2026-10-01

## 实现/复审
新增IssuerProcessConfig/run_issuer_process：精确IssuerDatabaseConfig和TenantScope、当前issuer UID/GID且不同于API、绝对私有路径、1–64连接、0–30秒accept timeout。监听前复验外部OIDC配置/0700 attempt及已有0750/0660 socket边界；复用原issuer listener/服务/数据库连接，不复制审批权威。
issuer IPC兼容新增expected_scope，新进程强制传入，帧scope不符在认证/attempt/DB前拒绝。decision连接工厂再次核验scope；read工厂始终绑定配置scope/数据库。每个accepted连接无论处理成功与否都计上限，finally关闭连接。
consumer原目录fd/inode/owner/父路径一致性清理提取aip_private_listener；consumer复用保持原合同，被替换对象和父目录不删。未知启动残留保留待对账，不宣称所有启动失败都无残留。

## 本轮验证
RED session69335：缺issuer process，exit2/0.41s。专项session13407：42 passed/4.82s/exit0。追加固定scope工厂装配单测后累计session21521：105 passed/13.64s/exit0，7已有warnings。git diff --check exit0。

```sh
services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_network_issuer_process.py services/aos-api/tests/aip/test_network_consumer_process.py services/aos-api/tests/aip/test_aip_network_issuer_ipc.py services/aos-api/tests/aip/test_network_consumer_config.py services/aos-api/tests/aip/test_network_consumer_cli.py services/aos-api/tests/aip/test_network_issuer_client.py services/aos-api/tests/aip/test_network_issuer_application.py services/aos-api/tests/aip/test_network_issuer_startup.py --tb=short --show-capture=no
```

真实Unix监听测试证明空闲退出、错误UID计数/禁入、own socket异常清理、占用/替换文件保留；consumer原父目录替换用例回归通过。跨scope帧测试注入peer仅到达scope门；工厂装配替身只验证绑定和关闭，没有真实批准效果。累计含此前TLS/JWT/API隔离测试，不代表当前正式身份。无UI变化，不做浏览器通过声明。

## 剩余风险与BG00FB
本波只对accept数量/空闲/帧读取设界，不是总业务耗时上限；issuer DB无完整SQL/事务时限。BG00FB优先检查并补签发连接超时及commit/rollback后限制保持，隔离真实PG验证后再进入私有配置/只读预检/CLI。当前生产实例未启动issuer；正式OS/OIDC材料、119–122部署与损坏启动载体仍独立恢复门。真实Event/八配置/Owner/Host/自然首链未完成。当前库只读、无商城源/旧Run/manual run_definition/Provider/230L0，不push。
