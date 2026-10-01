# BG00FY verification — fixed budget consumer admission

## 判定
连接/准入代码 GREEN；E17正式实例及自然首链 PENDING。a0v126未改；当前真实库无连接/迁移/激活/重启，Host/worker/Provider未启，商城源/旧12Run/230L0未碰。无UI修改，browser不适用。

## 证据
cwd services/aos-api。
- RED `.venv/bin/python -m pytest -q tests/aip/test_budget_consumer_connection_pg.py --tb=short --show-capture=no` → exit2，ModuleNotFoundError预算连接模块。
- 隔离迁移candidate生成 → exit1，缺受审manifest；审阅后才保存，没有从当前正式数据库自采通过基线。
- 首轮连接/schema/network：46passed/1failed，测试issuer与consumer共用了passfile。最小修正测试consumer独立0600文件，生产无凭据回退。
- 累计 `.venv/bin/python -m pytest -q tests/aip/test_budget_consumer_connection_pg.py tests/aip/test_budget_cost_preflight_pg.py tests/aip/test_network_consumer_connection_pg.py tests/aip/test_budget_cost_consumer_pg.py tests/aip/test_budget_cost_process.py --tb=short --show-capture=no` → exit0，82passed/32.20s。
- 追加只读消费拒绝和同签名函数体漂移后最终专项同RED命令 → exit0，16passed/5.80s。
- compileall 5个变更Python模块 exit0；首次cached diff检查发现两个新模块多余EOF空行，已修正并复验cached diff exit0。
- manifest SHA256 `9ae1b4ac752d53baa35da8a72ac75effdf8e39611c0bb5c91de547f18d4abd0b`，15tables/13functions。原6张issuer表和4个函数快照逐项完全一致；consume函数body与SQL源逐字一致。
- tests只在conftest独立aos_test_*_ti4_test全迁移库运行，真实低权限预算call LOGIN和真实TLSJWTissuer fixture；临时角色LOGIN/secret测试后还原，未启共享库开关。

## 方案及风险复核
network原require_consumer_identity抽取共享原语、错误类可由旧模块导入，连接行为不改；issuer公共API及manifest不变。预算端固定call/owner/function、READ COMMITTED、固定scope、无SET ROLE、精确dbname、loopback私有passfile且重验、禁止PG环境旁路、SQL限时和固定search_path。准入全catalog只读；异常含commit未知只抛对账要求不重发。连接事务终止后scope失效，必须新连接重验。

准入覆盖角色/成员/高权、表列ACL、额外owner表权限与函数ownership、约束/索引/RLS/trigger与函数定义；未通过不得yield业务连接。实际正向一次activation/失败整体rollback、只读拒写与漂移拒绝均在隔离库验证。

既有meta_membership无ENABLE/FORCE RLS（schema明确false），不得声称全依赖表RLS齐备。消费SQL两处成员查询显式org/project；caller无表读写、owner不可登录。此次不重写现有成员权限模型。

尚未具备原actor鉴权SQL/只读Receipt入口/有限消费进程；连接成功不代表可对外暴露API。下一BG00FZ补这条恢复链，之后接有限私有进程、产品自然消费和真实Task风险联合证明。正式OS/OIDC/DB身份配置、当前库版本实测/备份/克隆零执行窗口迁移仍独立恢复波，代码126不等于正式系统已最新。Watchdog仅方案未部署；Goal未变更。
