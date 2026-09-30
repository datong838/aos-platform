# BG00FF verification · 2026-10-01

基线69bcef83/AOS-001020；Task W5CB4-BG00FF-20261001。只补创建产品后端持久请求与只读恢复，无当前真实库写入/迁移/实例重启，无UI变化。

## 新鲜命令与结果
- `memory-status --json`强一致AOS/Prime CURRENT；`memory-validate --json`GREEN（1475 deliveries/1473 tasks/3911 events，Task前），exit0；eventual个人笔记STALE已知warning。
- RED：`services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_network_proposal_product_pg.py --tb=short --show-capture=no` 缺模块ImportError，exit2。
- 最小实现后同命令7 passed/9.56s/exit0；随后新增fsync失败及创建前失败用例。
- 最终累计58 passed/35.20s/exit0，7个既有Pydantic/Starlette warning；包含最终9项新专项：
```sh
services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_network_proposal_product_pg.py services/aos-api/tests/aip/test_network_proposal_reconcile_pg.py services/aos-api/tests/aip/test_network_issuer_product.py services/aos-api/tests/aip/test_network_issuer_application.py services/aos-api/tests/aip/test_aip_network_issuer_attempt.py services/aos-api/tests/aip/test_aip_network_policy_action_producer.py --tb=short --show-capture=no
```
- `git diff --check` exit0。逐文件复审新服务/router/测试，与先行方案一致；既有接口不变。

## 证明了什么
- TLS/JWT真实认证、临时aos_test_*_ti4_test PostgreSQL真实producer与BG00FD查询；测试内明确不是共享库。签名fixture不是正式账号证明。
- 真实PG创建提交后故障注入丢响应，后续GET/POST查回同proposalId；仅首次dispatch。proposal/draft各增1，其余approval/network head/revision/receipt计数不变。
- 两线程竞争O_EXCL槽，最多一次producer；中间未完整落盘可503但不能再dispatch，完成后GET查回。
- 相同slot不同expiry409；损坏/错actor/symlink/FIFO均503；其他身份看不到原请求；过期JWT HTTP401；记录不含token。
- fsync失败不dispatch、不删除槽；创建前异常后仍unresolved且不再dispatch。两类故障注入只证明安全合同，不作正式运行证据。
- 复用API受保护attempt_directory的独立namespace；稳定slot绑定scope/actor/policy/revision/headVersion。输入验证与4096byte上限在落盘前；0600文件及目录fsync完成才调用producer。
- GET从服务端恢复原body，客户端只需policy/revision/headVersion；不把body/token回传。PG仍裁定observed/conflict/unresolved，文件仅记录可能尝试。

## 限度与风险
本波无页面修改，未做浏览器验收；BG00FE真实空态截图不代表本波API上线。当前正式API未部署此入口。文件持久记录丢失/切换目录会破坏防重事实，正式部署必须绑定唯一API身份、持久路径、备份恢复；本波未证明完整灾难恢复。落槽后调用前中断也保持unresolved，不能盲重发；有证据证明无副作用后的正式恢复操作尚待产品实现。创建拒绝/失败后查询无记录不等于可以换key重发。
当前正式OS/OIDC、API启动载体修复、a0v118到122恢复波、配置Owner/Host/自然首链仍未完成。没有写真库/启Host/worker/Provider/读商城源/旧Run重放/手工Run/230 L0变更。Goal保障方案未实施，Goal状态未改。

## 下一波BG00FG
沿RuntimeNetworkPolicyPreviewPanel接候选提交与原请求查询，使用现有transport和统一收件箱深链；身份/候选变化时状态失效、unknown仅query；补正式恢复入口的无副作用证据合同，不把换key作为恢复。先方案/RED，专项累计、BrowserPilot真实适用边界、复审与精确收口。
