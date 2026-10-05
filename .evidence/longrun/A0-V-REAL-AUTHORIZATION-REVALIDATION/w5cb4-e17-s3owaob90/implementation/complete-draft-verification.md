# 完整命令草稿施工验证（未验收）

基线 m1@b1d64cc8，Authority AOS-001340；完整实现 Task/Lease 仍 ACTIVE。本记录没有提升整体阶段、last GREEN 或业务执行权限。当前代码尚未接正式 Service/API，当前真库未迁移、未读写、未启动业务 Provider。

## 入口草稿与证据边界

入口草稿包含原 native 同事务事实读取及 Binding/Receipt/proof 三写框架。五项 HTTPS OIDC/native 入口拒绝测试通过（complete-command-entry-green-r2.log，5 passed/9.18s），只证明入口拒绝，不证明八事实或 COMMIT。

entry-red/entry-green 首先因 ReleasePolicy positional ctor 错误失败，不是有效命令 RED。修正 fixture 后，临时更名草稿入口得到 corrected-red 的缺入口 ImportError，随后恢复入口取得五项通过。完整八事实正向、真正 COMMIT、回放/竞争/整事务回滚和 API 尚未验收，不能将这些草稿看作完成。

## 独立审查 Source 哈希修订

独立只读督导发现 Source proof 漏原 epoch。方案先增加原 epoch、安装 ID/etag、Owner 授权、Policy、Source request hash 序列化要求，再修改 evaluator 与原 signed Source 消费者测试。完整命令直接调用 `_source_proof_fact`，无新许可真源。

source-proof-epoch-red.log、red-r2.log 实际分别 1 passed/36.08s、1 passed/17.47s，但缺少完整触发组合，未执行新增 Source 分支，不能计作该项 RED/验收。保留原日志。

补齐 B88_SOURCE_REQUEST/B89_SOURCE_ISSUER/B90_SOURCE_CONSUMER 后，临时更名序列化入口取得 red-r3 的真实 ImportError（1 failed/33.89s）；恢复入口并增加 B90_JOINT_INPUT，green 实际 1 passed/35.52s。正向由原签名安装、Proposal、OIDC 批准、Source 发行、原正式 Source 读者与预算联合事实建立，不以手造许可替代。

新增断言从实际 Source fact 核对字段；人工副本改变 epoch/安装 etag/Owner 授权/Policy 后，原 SQL canonical_asset_registry_jsonb+digest 哈希变化。这只证明哈希敏感性，尚未证明正式 epoch 更新后的完整命令同 key 回放拒绝。独立督导复审结论：已实现，待完整命令验收。

相邻首次命令误用不存在的 test_binding_evaluator_connection.py，pytest exit4，未收集测试；已按真实 test_aip_binding_evaluator_connection_pg.py 重跑，完整 evaluator PG、strict contracts、native connection 相邻累计 116 passed/38.82s（complete-draft-source-adjacent-r2.log）。py_compile 与精确源码/方案 diff --check 已通过。测试重新产生的 Source/joint/锁图 JSON 记录是本次实测快照，前次原快照仍在基线提交中；它们不证明完整命令正向。

## 原 EvalContract 读者实际缺权与最小修订

实际 native SCRAM/SERIAL 下调用原 `_eval_blockers`，使用不存在的 Suite/Publication exact ref；RED 为原 SQL `permission denied for table aip_eval_suite_revision`，1 failed/6.13s（eval-reader-acl-red.log）。此为真实读取权限错误，不是正式业务正向。按先写方案合同，仅在 a144 SCOPED_READ 增加原 aip_eval_suite_revision 与 aip_publication_event 两表 SELECT，沿用原 ENABLE/FORCE/restrictive tenant 策略，无新写/锁权限。

最小修订后同原读者返回三个明确 missing blockers，1 passed/5.82s（eval-reader-acl-green.log）。实际角色读回两表 SELECT true/UPDATE false，canary 查询 0；canary 空表计数只证明此夹具结果，不能单独支持有数据时完整隔离。相邻原 RLS catalog 测试逐表验证 ENABLE/FORCE/restrictive。整个迁移只在一次性5433测试库应用，当前真库未迁移。完整 EvalContract frozen/READY 正向尚未验证。

修订后相邻累计 117 passed/38.59s（eval-reader-acl-adjacent.log），精确源码/方案 diff --check 与三修改 Python 文件 py_compile 通过。原完整命令入口拒绝、真实资源锁竞争、固定身份及原三写机制均保持原检查；没有完整命令正向证据。

两表权限修订后的原签名安装/Source消费者/预算联合回归另一次性库 1 passed/37.34s（eval-reader-acl-signed-regression.log），保留原普通角色签名路径；不覆盖完整 EvalContract 正向或下述最终 readiness 分支。

独立复审发现更深业务缺口：完整命令只查 frozen/current/hash，没有检查原动态 readiness/blockers。已先修订方案，再在原同一拒绝条件要求 ready 且 blockers 为空；该最后修订只有编译与源码一致性核对，不能借此前117通过声称完整合同拒绝已验证。原 frozen 合同缺依赖/撤销情况下的完整命令三写零增量测试仍待建立；Publication latest append 的并发撤销保护还未闭合。这些风险使本草稿保持未验收、不接正式入口、不迁移当前库。

## 原 frozen 维护故障拒绝验证

原合法 freeze 已要求 READY，因此没有借用重写 `_eval_blockers` 的 ReadyStore 测试生成业务正向。本次一次性 PG 维护负例用原 `_insert_eval` 注入缺 Suite/Publication/Gate 的 frozen 行，明确损坏夹具；原 get_eval_contract 返回 frozen/BLOCKED。新增正式私有消费者先 native admission，再原 head SHARE 和原 get_eval_contract(conn=同 native)，复用 current/hash/frozen/ready/no blockers 拒绝条件；完整命令实际直接调用，不接受替代回调。

RED 缺消费者 ImportError 1 failed/5.84s；最小移动既有读取段后 1 passed/6.45s；相邻累计 118 passed/40.47s。Binding/Receipt/proof 的 jsonb 全内容快照前后相等，强于只计行数。此证据只证明维护故障拒绝消费者，尚未穿过完整八事实命令，也未证明合法 freeze、Publication 并发撤销或完整 COMMIT。原三写完整Task依然ACTIVE。

独立只读督导实读确认同 native、无可替换回调、完整命令实际消费；动态 BLOCKED 拒绝可标 implemented/consumer verified，完整命令负例和 Publication 竞争仍 OPEN。最终三个 Python 文件编译、精确源码/方案 diff --check 通过。原始失败日志保留，日志行内原源码的空白不按源码 whitespace GREEN 覆盖。

## 合法原 freeze 与实际撤销竞争反证

本次复用原内容 Graph/EvalRunner 执行确定性内容预审和实际 Judge 比较，经原 derive_gate/publish/create/freeze 建立原 READY frozen 合同。没有 ReadyStore 重写，没有直接写 PASSED/frozen。资料/工件为隔离夹具、原执行有确定性测试适配器，不能当模型/路线目标评测或自然经营首链。

实际 native SCRAM/SERIAL 消费者读取合法 READY 后，保留原合同 head SHARE；第二连接原 ReleasePublicationService.revoke 在5秒内真正提交，旧 SERIAL 再次正式读取仍 READY，fresh native 则拒绝。Binding/Receipt/proof 全内容相等；读者最终rollback，不产生available/proof。初次1passed6.13s，改为绑定合同原 publication_ref 的精确event查询并记录JSON后1passed6.24s；相邻119passed39.20s。JSON记录原contract/revoke event/pubID/native PID及三表不变和commitSafe=false。这是安全缺口反证，pass表示复现缺口，不是修复通过。

独立只读督导确认原revoke published FOR UPDATE不更新该旧行，Authority.append也可直达INSERT；仅锁旧行无法保证writer先提交后的旧快照被拒绝。已将全 INSERT 中性 epoch、共享消费者、facts/hash、双向竞争、ONCONFLICT/rollback/ACL/canary与锁图验证登记在composition方案，尚未实施，不宣称已关闭。原合法 freeze链现在可复用到完整组合，但仍不是目标 Model/Route 八事实正向。

## 下一实质退出（保持完整范围）

继续同一完整 Task：原 signed 八事实完整正向及原 EvalContract reader ACL 实测；同调用方真实 COMMIT、所有异常完整回滚、同 key 原事实重验及实际撤销/安装/Owner/Policy 漂移拒绝；然后接正式 Service/API 与实例 ToolBinding。不能将此 Source 修订作为整波退出，也不再扩大 helper 准备替代完整命令。
