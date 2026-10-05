# b89 2026-10-05 07:38 施工检查点（非Delivery）

代码基线m1 28468f7e。Task w5cb4-e17-s3owaob89-complete-source-license-issuer-20261005 ACTIVE，Lease至09:00+08；本次未提交、未登记DONE。authority AOS-001329，七强投影CURRENT；memory-validate GREEN，delivery1785/event4843/task1784。九用户M及历史非本波未跟踪证据未修改。

## 实际文件变更与证据
- 新增 services/aos-api/aos_api/aip_license_source_issuer_contracts.py：复用原SecretStr命令base，严格ActionProposal批准ref（StrictInt revision>=2、裸64hex hash、exact ID），禁止actor/roles/grant额外字段；tenant/实际maker/完整批准ref进入原canonical_hash；token和key不入哈希。工厂重解析嵌套model_copy/construct并拒子类。返回值仅ISSUANCE_REQUEST_ONLY_NO_START。
- 新增 services/aos-api/tests/aip/test_source_license_issuer_pg.py：当前18项纯合同断言，尚无PG发行验收。跨租户canary仅哈希隔离断言，不称数据库或业务canary通过。
- 完善本目录plan.md：复用原RuntimeReleaseRevalidator与Registry原锁/实时时钟；记录SERIAL先建快照的消费风险和精确行锁待验证约束。未复制签名验证或证据选择算法。

RED red-contract.log实际为缺发行合同模块，pytest收集错误exit2，尚未执行断言；不称业务拒绝实证。初版green-contract.log 14passed/7warnings/4.62s。首次相邻命令漏test_aip前缀导致exit4未执行，完整保留green-contract-adjacent.log；修正r2为75passed/4.97s。补充各ref字段、tenant及子类边界后最新green-contract-adjacent-final.log **79passed/7warnings/4.61s**，四模块是issuer_contract/request_contract/source_action_gate/source_execution_gate。两新增文件py_compile及精确diffcheck通过。所有本轮测试handle均已terminal，未启动/重启PG测试库、未创建角色或使用真实JWT凭据。

## 尚未完成与精确接续
完整b89依然待实现，不能用本检查点替代交付：独立aos_source_license_issuer身份/专用SCRAM、a142最小ACL/RLS与DB写边界；原批准消费/当前maker和checker Owner/完整immutable信封；初始化锁首次独占与Registry当前性共同保证；同事务原issuance/head/RegistryReceipt；samekey对账/不同key冲突；真实签名正向与竞争、撤销、响应及提交失败回滚。下一先对专用角色/ACL和原批准消费写实际PG RED；修改原signed approval helper前另登记精确hook Task/Lease。不得先把Source事实读角色检查删除，也不得把测试Principal或公开请求合同当正式生产权利。

本轮原maker/checker模块未修改。真库aos_current_preview_20260927@a0v135只读，未迁移/重启；Host/worker/Provider/商城源/旧12Run/manual run_definition/外部效果未执行；没有新增真实模型调用，agnes r3 assessment6/7/O4限制保留。每日09职责及真实提醒迁移验证未被本合同测试代替。Goal保持active。
