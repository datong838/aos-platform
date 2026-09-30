# W5CB4 BG00dw｜签名 BI Plan 当前准入只读投影文件级方案

## 上位合同与现状

已复习 231/231-3/231-9：安装、配置、启用是不同状态；运营界面应给出正式缺口，但客户端不得自行算 ready。BG00ds 的写入口在一个事务锁安装、核验当前 OIDC Principal/持久成员角色与 markings、签名 approved 模板和六 active AgentInstance，写 draft Plan/Receipt。BG00dv 页面只提供只读引导，缺服务端结构化缺口。当前真库只读，正式正向条件缺失。

## 读合同

新增 `GET /v1/aip/production-contracts/responsibility-plans/bi-preparation/admission?installationId=<UUID>`。先检查 Principal 为同租户 OIDC；在读取安装、签名或六实例前，以当前持久 membership 和现有 `require_control_role` 判定配置角色。无身份、错租户、无成员或角色一律拒绝，不暴露安装存在性。对可读 actor，使用 scoped repeatable-read/read-only 连接读取当前安装 revision/ETag、approved/inactive 状态、lock 的 markings 和六 active 实例版本；复用 `require_target_markings` 保护安装细节。签名模板由现有 `ApprovedBIPreparationResolver` 选择并要求 installationId 精确一致，不从候选数或 URL 推断。

返回安装 ID、当前 revision/ETag、签名模板精确引用（仅核验通过时）、六角色 active 版本（仅授权可读）、按固定顺序的缺口 code 与 `candidateReady`。即使 `candidateReady=true` 也只是瞬时只读候选，**不得作为写授权或运行授权**；POST 始终重新锁定/复验。跨连接来源漂移时读结果最多是候选，不声称原子准入。读失败保守返回不可用/拒绝，不吞异常成 ready；不产生 Receipt、锁、outbox、worker 或 Provider 动作。

## RED 与最小文件

1. `services/aos-api/tests/test_ecommerce_business_investigation_aip_authority.py`：错租户/dev Principal 在 DB 前拒绝；无成员/角色在安装与签名读取前拒绝；缺 approved、签名、marking 或任一 active 实例给固定缺口；有齐全 test-only 读源时也只返回候选，不触发写接口/Receipt。隔离测试只证明读合同，不能冒充正式当前正向。
2. `services/aos-api/aos_api/ecommerce_business_investigation_aip_authority.py`：新增窄读 service，复用现有控制策略/签名 resolver，不复制写状态机。
3. `services/aos-api/aos_api/routers/aip_production_contracts.py`：新增 GET 只读路由与 response schema，认证 Principal 由依赖提供；不接收 actor、租户、权限布尔值。
4. 运行专项/相邻、OpenAPI/编译、只读当前实例负向；复审租户不可枚举、marking、快照漂移与方案一致性。browser-pilot 可用时再做页面验收；本波尚不改 UI。

回滚只反向本波代码/路由；当前 DB 不写、不启 Host/worker/Provider，不读商城源、不碰 dev-org 正向、不重放旧 12 Run、不手工 run_definition、不 push。
