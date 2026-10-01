# BG00GA verification — finite private budget consumer

## 范围与结论
有限私有进程/启动准入/显式check与serve入口代码 GREEN；正式跨OS UID链和自然首链 PENDING。迁移头仍127，本波无DDL；当前真实库无连接/写/迁/重启，无Host/worker/Provider，无商城源/旧Run/手工Run/230L0，无push。

## 新鲜验证（cwd services/aos-api）
- RED `.venv/bin/python -m pytest -q tests/aip/test_budget_consumer_process.py --tb=short --show-capture=no` → exit2，ModuleNotFoundError。
- 首轮consumer process + cost issuer process → exit0，40passed/24.00s。
- 累计 `.venv/bin/python -m pytest -q tests/aip/test_budget_consumer_process.py tests/aip/test_budget_cost_process.py tests/aip/test_budget_consumer_service_pg.py tests/aip/test_budget_consumer_connection_pg.py tests/aip/test_aip_network_issuer_ipc.py --tb=short --show-capture=no` → exit0，88passed/40.94s。
- 实际CLI进程 `.venv/bin/python -m aos_api.aip_budget_consumer_process --mode invalid-canary --config /nonexistent-canary` → exit2，stdout0字节，stderr仅BUDGET_CONSUMER_ENTRY_ARGUMENTS_INVALID，未回显参数。
- compileall三模块exit0；精确staged diff检查exit0。

## 证据与复审
复用原budget issuer配置/帧/peer/serve/有限loop抽取到aip_private_process；旧业务签发dispatch/receipt及listener admission保持，原18项process回归通过。公共循环仅传输不含业务SQL或attempt状态机。
BudgetConsumerProcessConfig固定独立BudgetConsumerConfig+栖月汇scope、API与consumer UID不同且当前euid/egid匹配、绝对短socket路径、连接数1..64/等待<=30s。启动先externalOIDC config、私有passfile、attempt目录、socket目录与未占用路径、只读数据库role/schema准入，再bind。每请求内核peer先于decode和业务，JWT/currentmaker仍由FZservice逐次校验。
真实隔离PG+TLSJWT dispatch消费及重建inquiry/重复原Receipt；实际Unix同UID拒绝且attempt为空、空闲有限退出、自己socket清理、替换路径保留。OIDC/凭据/目录/占用/错误DB/实际低权限role ACL drift均在bind前拒绝。私有配置拒绝额外DB user、错误tenant、重复字段和symlink；check不bind不消费；serve空闲退出。error响应固定不包含JWT/SQL异常；CLI明确businessAuthorized=false，ready不当业务授权。

## 剩余风险/下一波
测试配置apiUid为不同数值，仅用于负向peer测试，绝非已部署合法API OS身份；没有正式不同UID正向业务通信证据，不借高权账号或伪造身份。当前模块未注册后台自启，正式进程/配置仍需合法OS/OIDC/DB authority。
BG00GB接预算消费产品请求/稳定原请求恢复与IPC client，补批准后的合法投递入口、费用提议UI及development价格/预算政策producer，继续实际Task风险联合证明。当前真实实例最新重启门需独立身份版本实测、一致备份、克隆全链、零执行窗口迁移，不可用隔离pytest代替。Goal状态未改；Watchdog仅方案。
