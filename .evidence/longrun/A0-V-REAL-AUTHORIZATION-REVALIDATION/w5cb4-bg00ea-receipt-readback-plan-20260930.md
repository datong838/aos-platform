# W5CB4 BG00ea｜签名 BI 原命令绑定联合读回文件级方案

## 复习与边界

复习 231-3 安装生命周期/强 ETag、231-9 栖月汇首链与未知结果、栖月汇生意探究产品方案、BG00dy/dz。BG00dz 已让**新** BI Plan Receipt 同事务保存原安装 UUID/ETag、模板 exact ref、actor；BG00dy 的 GET 仍只返回 Plan ref 并固定 `installationBindingVerified=false`。旧 Receipt 无安装绑定，不能推断。原命令 Receipt 证明和当前可运行权威是不同问题：本波仅能证明当时写命令的绑定，不能跳过当前安装、身份、签名、配置、预算、审批、Host owner 的重验。

## 文件与最小设计

1. `services/aos-api/aos_api/aip_production_contract_store.py`：扩展认证读回 DTO，`installationBinding` 旧记录为 null，新记录经严格 UUID/正 ETag/exact template ref/actor 校验后返回；`installationBindingVerified` 与是否有已校验绑定严格一致；增加常量 `currentAdmissionVerified=false`。Receipt 查询继续固定租户/operation/原 actor/原幂等键，当前持久成员和配置角色先于 Receipt 查询，不增加写、锁或重发。错误/畸形绑定 fail-closed。
2. `apps/web/src/api/aipProductionContracts/contracts.ts/parser.ts/index.ts`：严格解析上述三字段，拒绝 true 却无绑定、false 却携带绑定、错类型/哈希/UUID/ETag/actor 空值；SDK 仍仅 GET，不产生幂等键，也不发 POST。页面保持禁写。
3. 后端和前端同波 RED；路由沿用现有 GET，不改写入口。若需要独立证明 Plan 当前仍存在，则另列只读 Plan 交叉核验波；本波字段名称仅表示 Receipt 存储的原命令绑定，不称当前 Plan/安装有效。

## 验证与停线

RED：新/旧 Receipt、跨租户/dev token、成员撤销/低角色、错 actor、畸形绑定、404 unknown；前端严格关系/无 POST。然后后端专项与 W2A/W2B 回归、前端专项/累计/TypeScript、OpenAPI、diff check。browser-pilot 可用时截图；不可用时记录限制。当前真库只读、Host/worker/Provider 关闭；不读商城源，不写 dev-org，不重放旧 12 Run，不手工 run_definition，不 push，230 L0 继续挂起。
