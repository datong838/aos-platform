# BG00EM 独立消费者服务实现验证

2026-10-01；authority AOS-001001；m1 HEAD 1f4b8284。本文件不是整波GREEN或当前实例授权证明。

## 已验证

- memory-status：AOS/Prime强一致投影CURRENT，eventual个人投影STALE；memory-validate GREEN，1450 Task / 1450 Delivery。未写个人记忆。
- Actor函数缺失时真实PG测试句柄73972：7 failed / 6.26s / exit1。连接层脱敏异常，不能把该输出解释为特定权限拒绝。
- 实现a0v_122原maker/当前owner-admin/精确Proposal-target-binding哈希门后，句柄9817：7 passed / 7.30s / exit0。
- 补只读事务强制、Receipt存在后成员降权拒绝、错误ApprovalEvent无写入/对账conflict后，句柄39789：92 passed / 29.75s / exit0。命令：

```sh
services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_network_consumer_actor_pg.py services/aos-api/tests/aip/test_network_consumer_contracts.py services/aos-api/tests/aip/test_network_atomic_consumer_pg.py services/aos-api/tests/aip/test_network_consumer_connection_pg.py services/aos-api/tests/aip/test_network_consumer_reconcile_pg.py services/aos-api/tests/aip/test_network_consumer_boundary_pg.py --tb=short --show-capture=no
```

- 上述PG路径使用独立测试库、真实事务/独立caller连接；合同测试仅验证输入形状。没有用测试身份验收正式实例。
- 当前真实库只读回读：`docker --context colima-aos-extension exec aos-a0v-recovery-pg psql -X -v ON_ERROR_STOP=1 -U aos_app -d aos_current_preview_20260927 -Atc 'BEGIN READ ONLY; SELECT current_database(),version_num FROM alembic_version; COMMIT;'` → `aos_current_preview_20260927|a0v_118` / exit0。
- `git diff --check` exit0；当前分支m1。无页面修改，不声称浏览器验收。

## 复核与剩余工作

写wrapper锁Proposal，再由120按subject排序锁双方成员并重验；不引入相反maker/checker单独预锁死锁。读wrapper STABLE、强制只读；历史Receipt也须当前原maker权限。PUBLIC无执行权，无新增表权限。内部120/121仍是可信DB caller原语，不能把wrapper当成对DB凭据持有者的隔离。

当前第4/9步仍进行中。外部OIDC验证、持久attempt reservation、一次性服务分派、真实失败/未知结果恢复组合验证尚未实现。没有开放HTTP/IPC消费，没有部署119–122到当前库，没有启Host/worker/Provider。代码/测试/计划未提交，两个BG00EM Lease仍ACTIVE，未推进authority。下一动作：扩展精确文件计划/Lease并接OIDC与持久attempt，避免以本次92项测试替代完整服务及真实首链。

## 00:44 身份与attempt增量

- AUTH/ATTEMPT补充Lease已登记，均同m1写者，authority仍AOS-001001。
- 新增`aip_network_consumer_auth.py`，复用外部配置检查与现有JWT resolver；缺模块RED句柄69682 exit2。consumer/issuer auth及consumer合同：句柄84439，49 passed / 5.10s / exit0。包含实际开发签名token被拒绝；resolver替身只用于适配器边界单元测试，不能当正式OIDC正向证据。
- 新增`aip_network_consumer_attempt.py`；现有issuer持久化提取内部helper，默认namespace=None时历史文件名及格式保持不变；consumer独立namespace。缺模块RED句柄18895 exit2。consumer/issuer attempt、auth、consumer合同：句柄74271，59 passed / 4.65s / exit0。
- attempt使用真实私有文件/O_EXCL并发八请求唯一赢家，精确request/subject冲突、残缺Unknown和模式异常拒绝；持久文件不存token。issuer/consumer同目录同key仍生成两个域隔离记录。
- issuer service相邻回归句柄81079：5 passed / 2 skipped / 4.00s / exit0。两个skip不得计为真实克隆服务验证。`git diff --check` exit0。
- 下一动作：接固定ConsumerDatabaseConfig服务入口及actor-aware SQL适配，先readonly当前actor门→独立attempt→至多一次写事务→独立readonly核Receipt；已attempted/Unknown禁止再消费。服务验证需覆盖实际PG事务和连接丢失后的只读对账，不能仅用mock服务测试收口。当前无服务分派实现、无正式外部身份与业务首链验收。四个Lease保持ACTIVE，未提交或推进authority。

## 最终代码验证与复审

上述为过程中检查点；现已实现固定config的私有消费/查询入口，尚无HTTP/IPC开放。SERVICE补充Lease已登记。缺模块RED句柄95961 exit2；首轮4 passed / 5.69s / exit0，句柄57494。补提交前回滚、预检后成员撤销、4并发单Receipt后，累计句柄82445：**142 passed / 2 skipped / 30.87s / exit0**。

```sh
services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_network_consumer_service_pg.py services/aos-api/tests/aip/test_network_consumer_actor_pg.py services/aos-api/tests/aip/test_network_consumer_contracts.py services/aos-api/tests/aip/test_network_consumer_auth.py services/aos-api/tests/aip/test_network_consumer_attempt.py services/aos-api/tests/aip/test_network_atomic_consumer_pg.py services/aos-api/tests/aip/test_network_consumer_connection_pg.py services/aos-api/tests/aip/test_network_consumer_reconcile_pg.py services/aos-api/tests/aip/test_network_consumer_boundary_pg.py services/aos-api/tests/aip/test_aip_network_issuer_auth.py services/aos-api/tests/aip/test_aip_network_issuer_attempt.py services/aos-api/tests/aip/test_aip_network_issuer_service.py --tb=short --show-capture=no
```

组合验证使用真实隔离PG、真实caller TCP、实际提交/回滚及私有文件。身份适配替身和注入连接故障仅证明分层组合行为；不是正式OIDC、操作系统进程隔离或真实网络断线验收。两项issuer环境skip不计GREEN。新服务在每次请求鉴权、精确函数属性/ACL检查后仅读actor门；unresolved才reserve；Conflict拒绝，Already/Unknown仅读；写/commit异常绝不重发；最终独立readonly Receipt是唯一observed来源。预检后撤权由同事务122/120重验，不以预检授权。

复审：issuer默认namespace None保持既有文件key/schema；consumer独立namespace避免相撞。没有更改全局鉴权默认值或新增开发fallback。数据库权限不扩表，旧120/121仍信任独立进程凭据，非不可信调用者安全边界。当前实例118只读，代码122未部署；没有读取商城源、重放Run、启动Host或worker、触230 L0。没有UI修改，不声称浏览器验证。

下一波BG00EN：优先正式外部OIDC与独立消费者进程的可用authority审计；补无需resolver替身的签名/租户/过期验证与服务端到端隔离证据，随后按独立迁移部署门推进当前实例。缺真实身份时继续安全独立实现，不能虚造账号或以142测试替代当前业务首链。
