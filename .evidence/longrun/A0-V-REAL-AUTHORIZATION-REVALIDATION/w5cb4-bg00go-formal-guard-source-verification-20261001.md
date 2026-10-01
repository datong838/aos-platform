# BG00GO 进行中验证记录（不是交付收口）

基线 AOS-001055 / m1 eedf02e6fe8b4461524fab861cb83142578ed9b2。Task W5CB4-BG00GO-20261001 保持进行中。本记录对应工作树，尚无本波提交；authority、Delivery 与首链状态未推进。

## 已执行与边界

- `scripts/memory/memory-status --json`：七个 strong CURRENT；个人 memory eventual STALE 保留，未写个人记忆。
- `scripts/memory/memory-validate --json`：GREEN，1513 Delivery / 1512 Task / 4025 events，exit 0。
- a0v129 仅在 pytest 完整迁移临时库运行；当前真实库未连接、未迁移、未重启。Host/Provider 未开启。
- 首轮边界测试 session 52202 已回读终态：6 passed / 4.32s / exit 0。
- 新来源测试 RED：`/tmp/aos-go-source-red.log`，6 failed / 6 passed / 4.71s / exit 1，缺少正式来源模块。
- 最小来源实现后：`/tmp/aos-go-source-green.log`，12 passed / 4.55s / exit 0。
- maker RED：`/tmp/aos-go-maker-red.log`，2 failed / 10 deselected / exit 1，缺少专用 maker 接口。
- maker 首次复验失败在隔离夹具缺 workspace；补后暴露缺 org；补合法 FK 父项后暴露 ActionStore.create_proposal 仍仅允许 Network guard。均保留失败日志 `/tmp/aos-go-maker-green{,2,3}.log`；没有关闭约束或放开通用生产接口。
- maker 最后专项：`/tmp/aos-go-maker-green4.log`，14 passed / 4.75s / exit 0。
- 累计：`/tmp/aos-go-maker-regression.log`，78 passed / 18.88s / exit 0；7 个既有 warnings。命令如下。
- `git diff --check` 与五个本波 Python 文件 compileall 均 exit 0。
- 文件发现中两个猜测的测试路径不存在（shell glob/sed/rg 非零）；随后用 rg --files 找到实际文件，未据此报告测试通过。

```sh
cd services/aos-api
.venv/bin/python -m pytest \
  tests/aip/test_guard_policy_activation.py \
  tests/aip/test_guard_policy_activation_pg.py \
  tests/aip/test_aip_policy_activation_action.py \
  tests/aip/test_aip_network_policy_action_producer.py \
  tests/aip/test_aip_runtime_guard_policy_contracts.py \
  tests/aip/test_content_first_action_binding.py \
  tests/aip/test_content_first_action_binding_pg.py -q
```

## maker 阶段实现与证据限度（后续增量见下文）

1. a0v129 的元数据及 active 写边界已测；独立低权消费函数尚未安装，角色仍不可用于正式激活。
2. `aip_guard_policy_activation.py` 验精确 Draft/payload/hash/tenant/head/原 publish Receipt。active 候选只能 revision+1、lifecycle 改变，其余内容相等；构造器绕校验会重新验证。绑定 source/target hash、scope、Action、head version。
3. 专用 maker 经原 ActionStore 写 drafted Proposal 与 Draft；正式 metadata、当前 owner/admin、源 head 与有效期在同事务重验。原通用接口仍禁入；checker 尚未接线，不能通过此模块批准。
4. PG maker 测试的 Principal 和成员是明确隔离夹具，**没有验证真实 JWT**。来源/Proposal/Receipt 走真实数据库和原 Store，不冒充当前真实组织身份或完整授权链。
5. 专项证明幂等 maker 读回、成员撤销后拒绝、无 Approval/active 修订；不代表全套并发/未知结果/消费端覆盖。累计包含原 Network producer 单元门与 Content binding，尚非全部 Network PG 历史夹具回归。

## 独立 checker 与签名入口增量

本增量仍是同一 BG00GO Task、同一未提交工作树。开工复读 AOS-001055、七 strong CURRENT、validate GREEN（1513 Delivery / 1512 Task / 4025 events），未改变 authority。

- 新 `aip_guard_policy_issuer.py`：external-only HTTPS OIDC、每请求 JWT 验证、严格重解析输入、真实私有 issuer 数据库身份、命名空间持久 fsync 防重发、原 Event 只读对账；没有默认 issuer credential/factory。
- `GuardPolicyApprovalGuard` 接原 ActionStore.decide：当前独立 checker、当前 maker、固定 metadata、精确 source/head、原 Draft 与批准策略 hash、无旧决定/撤回、数据库时限。`decide_guard_activation` 以外层事务包住原 Store，最终 clock_timestamp 超期即整个批准回滚。
- 签名 RED：`/tmp/aos-go-checker-red.log`，6 failed / 12 deselected / 8.45s / exit 1（缺 issuer 模块）。
- 初签名专项：`/tmp/aos-go-checker-green.log`，20 passed / 9.11s / exit 0。
- 故障专项：`/tmp/aos-go-checker-faults.log`，24 passed / 12.48s / exit 0。
- 最后累计：沿上文同七组命令，`/tmp/aos-go-checker-regression.log`，**88 passed / 26.99s / exit 0**，7 既有 warnings。与前面 78/24 不相加。
- diff --check 与 activation/issuer/ActionStore/PG-test compileall exit 0。

两类策略均实际 HTTPS JWKS / RSA JWT 验证 maker，再由另一签名 subject 和实际独立 SCRAM PostgreSQL LOGIN 写原 ApprovalEvent。测试身份是隔离 IdP 与临时成员，不是当前真实客户身份；临时 passfile 0600，角色在 finally 恢复 NOLOGIN/PASSWORD NULL。原批准 event/hash 全经生产 Store 写，不手填。

已测自批、成员撤销、错误签名、跨 tenant 拒绝且无 attempt/Approval；普通 runtime 假充 issuer 拒绝。连接故障注入分别发生在实际决定事务 commit 前/后，重复调用无新决定：前者始终 unresolved/0 Event，后者 observed/1 Event。持久 marker 仅记公开标识/hash，不记 token。过期测试在真实 INSERT 增加延迟 trigger，并用不随 rollback 撤销的临时 sequence 验证确实到达 INSERT；outer clock 检查使 Approval/Proposal 变更回滚。没有停用任何批准/租户约束。

实现过程一次补丁把 maker replay 后半段误放在新 checker 类返回语句后，工具回读发现并在运行测试前纠正，最终累计包含 maker 当前成员撤销/幂等回读。查找 migration128 时一个猜测文件名不存在，随后 rg --files 定位实际 `a0v_128_budget_cost_configuration.py`；未把失败读取计为验证。

### checker 阶段剩余边界（后续消费增量见下文）

签名 checker 的 observed 仅证明原决定写入，返回 `activationAuthorized=false`；不能视为 active 配置或完整首链。消费 SQL/Python、caller 低权边界、Provider 依赖联合读取、并发/撤销与消费时过期仍未实现/验证。当前实例未连接、未部署迁移、未开启 Provider/Host、未浏览器验收。

## 继续入口：BG00GO 第4/9步

### 低权消费增量（仍未收口）

- 当前 m1 HEAD 仍 eedf02e6；七 strong CURRENT，validate GREEN，AOS-001055 与 Task 未关闭。新 SQL/Python/migration 均仅在工作树。
- `aip_guard_policy_consumer.sql` 和 `aip_guard_policy_consumer.py` 已实现；a0v129 安装独立 caller/owner RLS、仅 caller 执行的 security-definer 函数、精确表/列授权，保护 active 修订/head/Receipt 必须同时为 consumer session/current_user。函数内部也要求写 SERIALIZABLE、读 REPEATABLE READ READ ONLY。
- 实际正向链：原 Store Draft/Receipt→签名 maker 原 Proposal/Draft→独立签名 checker 原 ApprovalEvent→签名 maker 经独立 SCRAM caller 消费→两种 active2 修订及原 guard Receipt→原 require_provider_dependencies 读取两种精确产物。reader 的 endpoint/ref 输入容器是 SimpleNamespace；**未发布真实 ProviderInstance、未调用 Provider、未验证完整 ModelRoute 或业务首链**。
- RED `/tmp/aos-go-consumer-red.log`：1 failed / 22 deselected / 5.23s / exit 1，缺 consumer 模块。
- 正向初验 `/tmp/aos-go-consumer-green.log`：1 passed / 22 deselected / 5.56s / exit 0。
- 专项 `/tmp/aos-go-consumer-faults.log`：36 passed / 22.94s / exit 0；错误 target/binding、错误 actor/JWT、跨 tenant、checker 撤销、source head 前进、原批准 withdrawal 均在 attempt/Receipt 前拒绝；consumer commit 前/后断联各仅调用写函数一次；caller 无表读取/role 切换权限。
- 累计 `/tmp/aos-go-consumer-regression.log`：上文七组命令 **101 passed / 36.93s / exit 0**。包含新增并发消费：单一持久 marker，竞态可 unresolved，最终独立只读查询 observed，恰好一条 Receipt。
- 随后补历史 Receipt 的原产物列/payload/hash/ApprovalEvent 一致性复核，定向 `/tmp/aos-go-consumer-final.log`：4 passed / 31 deselected / 7.97s / exit 0。最后又收紧 source head 数字类型，当前 SQL 的正向复验 `/tmp/aos-go-consumer-exact-final.log`：1 passed / 34 deselected / 5.37s / exit 0。
- diff --check、consumer/migration/PG-test compileall exit 0（最终 SQL 类型收紧不涉及 Python）。没有修改当前实例、数据卷、服务状态或已有正常业务数据。

### 累计兼容失败必须修复

`tests/aip/test_aip_runtime_guard_policy_store.py` + `test_aip_runtime_guard_policy_api.py`：`/tmp/aos-go-history-red.log`，**1 failed / 9 passed / 28.86s / exit 1**。失败精确为 `test_guard_policy_store_requires_exact_active_effective_refs`，旧 `_runtime_guard_history_fixture.seed_historical_runtime_guard` 直接 INSERT active 被新 GUARD_POLICY_CONSUMER_REQUIRED 正确拒绝。共有7个文件引用旧 helper；不能放宽生产触发器、不能跳过该测试或以本轮101替代此失败。

下一施工项：登记额外测试文件 scope，改需要 active 来源的兼容测试为新签名批准/低权消费来源；复习硬编码历史时间和 revision1 断言，保持 reader 的到期/精确版本/租户隔离覆盖。真正迁移前历史恢复场景需单独的恢复证据，不通过关触发器或借高权限制造“正式来源”。未改旧 fixture，未新增租户侧业务写。消费端过期/并发扩展审查与全套旧 Network/Model reader 回归仍需补齐。此失败不阻断可独立研发，Goal 保持 active。

- 专用 checker、签名入口与独立 LOGIN 专项已有上述证据；继续审查 source 漂移、已批准后的历史查询与 marker 篡改等边界，不能扩大为真实身份验收。
- 两种低权 consumer 正向已有上述证据；继续补消费端时限/旧兼容回归与复审，不扩大为当前实例部署或首链完成。
- 完成后补全累计回归/方案复审，再精确提交、Task/Delivery/CAS/Prime、449 接续与 D-waves。当前不得提前关闭 Task 或宣称首链通过。
- 后续完整 Review→AgentRun→首生批准→Capacity→GE held 与当前实例恢复波、自然首链、八场景仍保留。

## 来源兼容修复与消费中到期验证（仍未收口）

重新开工：m1 eedf02e6；AOS-001055；七 strong CURRENT，validate GREEN（1513 Delivery / 1514 Task / 4027 events），输出 /tmp/aos-go-resume-status.json、/tmp/aos-go-resume-validate.json。旧读取命令误用代码仓 docs 相对路径，返回不存在；随后改读 ../docs 正确权威文件。

旧 Guard helper 已改为原 Store draft→signed maker→独立 signed checker→低权 consumer，返回 active2。TLS/临时独立 LOGIN fixture 移入中性 helper，在 conftest 惰性注册，未调用来源的测试不启动它们。Model Runtime 的 Network 来源也经已有正式 producer/issuer/consumer；原历史 Network reader 的人工种子不计正式来源。

- /tmp/aos-go-fixture-focused.log：41 passed /26.96s /exit0。
- /tmp/aos-go-fixture-compat.log：2 failed /21 passed /28.06s /exit1，Model 旧直接 active Network INSERT 与 TLS 请求零基线错误。
- /tmp/aos-go-fixture-compat2.log：1 failed /11 passed /13.66s /exit1。当时 Model 修改命令的重复目录前缀导致 FileNotFound，仍测试旧代码；已改绝对路径完成修复。
- /tmp/aos-go-fixture-model.log：Model Runtime 3 passed /5.59s /exit0，修复后实际来源链通过。
- 新消费中审批到期测试首次 /tmp/aos-go-consumer-expiry.log：2 failed /35 deselected /5.85s /exit1，测试目录 consumer 与 fixture 已创建目录重名，未到业务写入。改为独立 expiry-consumer-attempts。
- /tmp/aos-go-consumer-expiry-final.log：2 passed /35 deselected /8.72s /exit0。两种策略均实际到达 Receipt INSERT（sequence is_called），最终 unresolved，active=0、head=(1,1)、activationReceipt=0、原 ApprovalEvent=1。未停用安全触发器；故障注入对象 finally 清理。

这些全是全迁移临时 PostgreSQL、隔离签名身份测试；不证明当前正式组织身份/部署/首链，不证明今日当前系统全面重启。消费最终 clock_timestamp 安全门无需生产改动。累计16组正在执行，结束后以实际输出补记，不提前声明 GREEN。

一次 Python stdin 追加文档遇编码错误，文档未写入；已改 shell literal heredoc。compileall 与 git diff --check exit0。

### 累计顺序污染定位

/tmp/aos-go-final-regression.log：16组 136 passed /46 failed /98.06s /exit1。46例均 GUARD_OBJECT_METADATA_DRIFTED。定位 tests/conftest.py client fixture 清理 SQL 删除所有非四种演示对象；前序 Network API 测试使用 client 后把 a0v129 的两个正式 Guard 对象删除，后续正式来源正确拒绝。已先补方案，再仅在清理排除集合增加 EgressPolicyRevision 与 DataClassificationPolicyRevision。没有重建来源、放宽 metadata 一致性或跳过测试；相同16组顺序复跑 /tmp/aos-go-final-regression-r2.log。

/tmp/aos-go-final-regression-r2.log：141 passed /41 failed /102.36s /exit1。Guard 元数据来源问题已解除；剩余全部 FORMAL_NETWORK_OBJECT_TYPE_UNAVAILABLE，同一 client 清理还删掉既有 NetworkPolicyRevision。方案补充后将此正式对象一并保留，生产代码无改动，原16组继续 /tmp/aos-go-final-regression-r3.log。

/tmp/aos-go-final-regression-r3.log：181 passed /1 failed /123.24s /exit1，仅 Network Receipt 后到期等待未到达。单独复现 /tmp/aos-go-network-expiry-repro.log：1 failed /8.30s /exit1。定位惰性 Guard issuer 使用并覆写已有 Network private_passfile。已给 Guard issuer 独立 guard-issuer-pgpass（0600），finally 只擦除自己文件，原测试不改、不延长等待。/tmp/aos-go-passfile-isolation.log：原 Network 失败用例 + Guard PG 全组 38 passed /32.52s /exit0。此修复是测试身份文件隔离，不改生产权限。

## 本波最终累计与复审

最终 /tmp/aos-go-final-regression-r4.log：182 passed /7既有warnings /126.48s /exit0；与前面专项不相加。API目录执行 `.venv/bin/python -m pytest` 以下16文件加 `-q`：

- tests/aip/test_guard_policy_activation.py
- tests/aip/test_guard_policy_activation_pg.py
- tests/aip/test_aip_policy_activation_action.py
- tests/aip/test_aip_network_policy_action_producer.py
- tests/aip/test_aip_runtime_guard_policy_contracts.py
- tests/aip/test_aip_runtime_guard_policy_store.py
- tests/aip/test_aip_runtime_guard_policy_api.py
- tests/aip/test_aip7_model_runtime_store.py
- tests/aip/test_aip_network_policy_store.py
- tests/aip/test_network_approval_precheck_expiry_pg.py
- tests/aip/test_network_consumer_signed_https_pg.py
- tests/aip/test_network_atomic_consumer_pg.py
- tests/aip/test_network_consumer_actor_pg.py
- tests/aip/test_network_consumer_connection_pg.py
- tests/aip/test_content_first_action_binding.py
- tests/aip/test_content_first_action_binding_pg.py

最终 compileall（activation/issuer/consumer/migration/公共fixture/conftest）与 git diff --check 均exit0。复审已核精确两Action专用接线、固定metadata、maker/checker成员及源head核验、独立低权角色、不可变批准与Receipt、末端到期回滚、未知结果不重发、私有凭据文件隔离。未扩大通用生产入口；UI无变更，本波浏览器不适用。工作树中其他browser/pnpm及现场证据不纳入提交。

本波代码门可收口；HTTP/UI产品入口、真实外部身份与当前实例独立恢复部署、完整合法Review→AgentRun→首生批准→Capacity→GE held、自然首链、八场景及发布决定均未证明。当前migration129仅临时库演练，真实库未连接、未迁移或重启，Host/worker/Provider保持本波未操作。下一波必须回到完整首链来源联合，不得以182测试替代业务验收。看门狗保障方案仍未部署。Goal保持active。
