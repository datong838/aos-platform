# W5CB4 BG00dr｜signed-approved BI 配置入口与真实 actor 文件级方案

## 上位合同与现场

已复习 231 主计划、231-3 的安装/配置分离及 231-9 的六数字同事共用 AIP 权威。BG00dp 已证明 growth1.12 签名 approved 安装可只读选择精确 BI 模板，但当前真库只有 growth1.11，clone 只有 approved1.12；没有正式三身份、Host assignment、八配置候选或自然首链。当前库保持只读。

现有 `POST /v1/aip/production-contracts/responsibility-plans` 从 `require_principal` 取得 `principal.subject`，但默认 `AipProductionContractStore` 使用 active 内容解析器，approved 签名模板无法从此入口创建 Plan。`BusinessInvestigationAuthorityMaterializer.ensure/finalize_responsibility_plan` 和 `BusinessInvestigationBindingReadinessCoordinator.refresh` 有 `aos-main-development` actor 默认值；脚本另传固定开发 actor。这些仅是历史开发路径，不能作为 E17 正式账号/权限/Receipt 证明。物料化器目前按 Stage 创建/冻结、Plan 创建/冻结跨多个事务，单纯在写前加一次成员查询会有安装和权限漂移窗口。

## 要达到的产品行为

用户通过已认证产品会话为精确 `org-org/dev-project` 的唯一 approved 签名安装准备 BI Plan。服务端在实际写事务中核验当前持久成员资格与所需角色/marking、安装 state/ETag、composition lock/签名/alias/模板字节、六个当前 AgentInstance 及能力绑定；请求只承载 exact 目标与 Idempotency-Key，不承载 actor、模板内容或高权限布尔值。每次写的 Receipt 记录 `principal.subject`、安装/模板 exact ref 和请求哈希；重放只读回同一结果，漂移/撤权在写前失败。配置准备不能变成 active/enable，也不能触发 worker、Provider 或业务 Run。

## RED 与最小施工顺序

1. 在 `services/aos-api/tests/routers/`（新增精确测试文件）及 `tests/test_ecommerce_business_investigation_aip_authority.py` 写 RED：dev token/任意 actor、错租户、无持久成员/角色/marking、approved 安装漂移、非唯一安装、签名/lock/alias/模板变化、缺六实例、重放异 body 均不得留下 Stage/Plan/Receipt；合法当前 actor 只在 test-only 克隆证明配置准备，不声称正式首链。
2. 先审 `asset_registry/installation_store.py` 当前锁与 `extension_runtime/current_permission.py` 的事务要求，以及 `aip_production_contract_store.py` 责任计划插入/Receipt 原语。若无法在同一事务或有界多步骤 Receipt Saga 中同时完成安装/权限复核和 Plan 写入，先补窄事务接口与恢复合同，再开放产品路由；不采用路由层一次预检后调用普通 Store 写入的 TOCTOU 方案。
3. 只改必要文件：`routers/aip_production_contracts.py` 增加明确的 signed-approved BI 准备入口；`ecommerce_business_investigation_aip_authority.py` 移除默认开发 actor，接收不可伪造的当前 principal/受信权限上下文；`ecommerce_business_investigation_aip_readiness.py` 同步显式 actor；如第2步证明需要，扩展 `aip_production_contract_store.py` 窄事务原语及其测试。UI 入口另波对接，不从前端直传 actor。
4. 专项/累计、克隆签名只读及适用时产品浏览器验收；独立复审身份/权限/Receipt/恢复。正式当前实例缺签发/checker/三身份/Owner 时仍只读，不把 test-only 正向升级为当前授权。

## 事务审计补充

`PostgresInstallationStore.lock_for_transition_in_transaction` 在调用者连接中取安装行 `FOR UPDATE` 并校验 ETag；`CurrentControlPermission` 在同一事务内查 `meta_membership FOR SHARE`、marking tuple 和当前 composition lock。相反，`AipProductionContractStore.create_stage_template/create_responsibility_plan` 各自打开连接、提交独立 Receipt；现有 `Materializer.ensure` 跨 Stage/Plan 多次提交。因此不能只在新路由里调用 `CurrentControlPermission` 后再调用 `ensure`：锁释放后安装/成员可改变，Stage 可能留下而 Plan 未建。BG00dr 代码波须先明确单事务窄原语或带精确状态/补偿的 Receipt Saga，并用并发撤权/安装变化反证。

回滚仅反向本波代码/路由，不改当前库或既有 Receipt；不读商城源、不写 dev-org、不重放旧 12 Run、不手工 run_definition、不启 Host/worker/Provider、不 push。
