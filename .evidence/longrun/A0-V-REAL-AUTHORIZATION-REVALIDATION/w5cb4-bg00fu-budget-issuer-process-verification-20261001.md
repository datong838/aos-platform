# BG00FU schema准入/独立预算签发IPC verification

基线AOS-001035 / m1@0b0586d4；Task W5CB4-BG00FU-20261001。方案见同目录plan文件。

## RED/排障/验证
- 新schema测试缺模块RED：exit2/0.40s；迁移隔离库capture后manifest尚未登记拒绝exit1（未从正式库生成基线）。逐项核对五表列/PK/FK/CHECK/唯一索引/RLS/策略/触发器和两函数正文/ACL，登记源迁移hash与manifest hash于plan。
- 首schema9passed/4.49s；owner转移专项真实RED：ALTER FUNCTION extension_reject_history_mutation OWNER TO network issuer未被拒绝，exit1。修正为精确aos_app Owner，后续负例通过。
- 首IPC 15passed/2failed/15.15s；失败AF_UNIX path too long。改短专属fixture并为生产config加103bytes上限。下一轮26passed/2failed/15.59s，失败临时目录继承/tmp GID不符，fixture chown自身GID后通过；未放宽production路径/权限校验。
- 累计命令：`services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_budget_cost_preflight_pg.py services/aos-api/tests/aip/test_budget_cost_process.py services/aos-api/tests/aip/test_budget_cost_connection_pg.py services/aos-api/tests/aip/test_budget_cost_issuer_pg.py services/aos-api/tests/aip/test_budget_cost_proposal_pg.py services/aos-api/tests/aip/test_aip_network_issuer_attempt.py services/aos-api/tests/aip/test_aip_network_issuer_service.py services/aos-api/tests/aip/test_aip_network_issuer_ipc.py services/aos-api/tests/aip/test_network_issuer_process.py --tb=short --show-capture=no` → 120passed/2skipped/7warnings/42.08s/exit0。
- 末次增加runtime额外角色负例并收紧成员拒绝异常断言：新两文件专项29passed/7warnings/13.21s/exit0（11schema+18process）。不将120+29相加；2skip属历史network专用clone测试，不能算通过。
- compileall四Python文件、git diff --check退出0；alembic heads a0v_125/exit0，未新增迁移。临时日志 /tmp/aos-fu-{red,catalog,owner-red,schema-green,process,green,regression,final-targeted}.log 可复核。

## 真实证据与限制
schema preflight只读pg_catalog，不读商城源/业务行；manifest来自本次隔离迁移库，生产不能自动采纳现场结构。五表44列/27约束/7索引、两guard函数精确结构；owner固定aos_app、runtime无高权/额外角色/CREATE。检测disabled trigger、RLS/force、约束/策略/列级与PUBLIC授权、函数正文及owner漂移。平台受信迁移仍须零DDL窗口，不宣称抵御同时恶意DDL。
连接复用FT，schema每次新连接都检查；listener先外部OIDC/私有目录/只读DB预检，再有限accept。配置固定scope、distinctUID/currentUID/GID、绝对path、103bytes Unix路径、最多64连接。wire64KiB/重复JSON键/NaN/bool版本/非法payload拒绝，复用既有kernel peer和frame代码。
service实际隔离PG/private登录+TLS JWT完成批准/原ReceiptInquiry/撤销；批准eligiblefalse，无budget active/Provider。私有attempt复用O_EXCL/fsync原语并按预算域/actor/operation隔离，hash不存JWT/body；重复execute_once只Inquiry，冲突不重发。故障注入仅模拟第一次execute前/提交后断联，后续重建service不能再写，真实PG行数0/1对应unresolved/observed。替身只用于断联/不重发断言，不是业务验收。
Unix监听/同UID客户端内核拒绝/自有socket清理与替换文件保留是真实OS测试；未建立正式不同OS UID正向端到端，不伪称正式签发进程部署。没有HTTP/UI改变，浏览器不适用。

## 下波
BG00FV产品私有客户端及原请求持久恢复（原actor/资源/operation/body/key），刷新后unknown仅Inquiry；原子consumer锁当前批准/撤销/head/source写active和唯一Receipt仍待。正式OS/OIDC/DB凭据与launch配置、安全备份克隆/迁移当前实例另波，不能把本波当当前系统已最新。
当前真实库零连接/零写/零迁移/零重启，Host/worker/Provider关闭，无旧12Run/手工Run/230L0/no push。首链未完成，Goal保持active；防停工方案未实施。
