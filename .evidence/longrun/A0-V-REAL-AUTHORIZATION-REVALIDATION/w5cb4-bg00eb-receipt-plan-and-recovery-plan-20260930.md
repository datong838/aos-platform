# W5CB4 BG00EB｜签名 BI Receipt→Plan 核验与未知结果只读入口文件级方案

## 上位合同与边界

复习 231-3 安装与 ETag、231-9 未知结果先对账、栖月汇生意探究方案、BG00dy/dz/ea。BG00ea 的 GET 已固定正式 OIDC、当前成员/配置角色、tenant/operation/actor/原幂等键，却仅解析 Receipt 内 Plan exact ref；还未在同一只读快照核对持久 Plan。当前库、Host、worker、Provider、商城源和旧 12 Run 均保持原禁入状态。

## 文件级最小改动

1. `services/aos-api/aos_api/aip_production_contract_store.py`：Receipt 取出 exact Plan ref 后，在现有 `connect_read_only` 的 repeatable-read 事务中按租户、plan_id、revision 查 `aip_responsibility_plan_revision` 的 content_hash、created_by、template_ref。缺行、hash/actor 漂移、原绑定模板与 Plan 模板不一致均 fail-closed；旧无绑定 Receipt 只核 Plan/hash/actor，不倒推安装。成功增加 `planRevisionVerified=true`；`currentAdmissionVerified=false` 不变。无新写、锁、重发。
2. `services/aos-api/tests/test_ecommerce_business_investigation_aip_authority.py`：RED 覆盖旧/新 Receipt 正向、Plan 缺失/hash/actor/template 漂移、只读 SELECT 与同连接、原 actor/租户固定；原权限负例继续通过。
3. `apps/web/src/api/aipProductionContracts/{contracts,parser}.ts` 与 `parser.test.ts`：要求并解析服务端 `planRevisionVerified=true`，拒绝缺失/false；现有 SDK 测试同步新字段，不扩大为当前安装准入。
4. `apps/web/src/pages/s2/ProductionContractsPage.tsx` 与测试：在有效来源安装上下文显示可选只读对账入口。用户手工输入**原始**幂等键后才调用现有 `readSignedBIPlanReceipt` GET；不从 URL 猜键、不生成键、不保存、不自动 POST。键为空/带首尾空白/超过120字符不查询。成功仅展示原 Plan 修订与原绑定；绑定安装与来源不一致、旧 Receipt 无绑定、403/404/网络未知分别保守提示，不显示“当前可运行”。切换来源或键后旧结果不得混入新上下文。

## RED、验证与收口

先写失败测试，再改上述最小实现。运行后端专项及既有七文件累计、前端 parser/SDK/页面专项及累计、TypeScript、OpenAPI/静态检查；适用时 browser-pilot 截图。无 browser-pilot callable 时如实登记限制，不拿测试当浏览器验收。核对 `git diff --check`、方案一致性、正式来源只读审计，再写 verification、D-waves 下一波、m1 精确提交及 AOS/Prime 权威同步。未知结果和正式来源缺失不授权重发或开启 Host。
