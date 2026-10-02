# W5CB4 E17｜原签名 BI Plan 跨安装状态受控重绑定方案

## 上位事实

- 231-3 规定 approved→runtime-apply/verify→active，配置 `roleRefs` 只认当前、精确、已冻结的 `ResponsibilityPlanRevision`；Plan reader 不授业务执行权。
- BG00ds 的 `SignedBIPlanPreparationService.prepare` 只在 approved inactive 安装下，用正式 OIDC actor、当前持久权限、强安装 ETag、签名模板和六 active 实例原子创建 draft 与 `bi_responsibility_plan.prepare` Receipt。
- 550 的原 Registry/OCI/安装链证明 verify 后模板哈希不变而安装修订号改变，业务读者必须拒旧模板 exact ref；旧 draft 因而不能直接冻结。
- `SignedBIPlanReceiptReader` 是历史只读证明，`current_admission_verified=False`；通用 `revise_responsibility_plan` 自己开事务，不锁原安装也不复核 prepare Receipt，不能直接作为签名 BI 状态接续入口。

## 本波边界与文件

1. `services/aos-api/aos_api/aip_production_contract_store.py`：把现有 Plan 修订写入抽为 caller-held transaction 原语，保留通用路由原语义；专用操作使用不同 operation 名和绑定原 Receipt/安装状态/Plan 版本的请求哈希，重放严格同 body，异 body 拒。新 Receipt 写入原准备 Receipt ID、安装 ID/ETag、旧与 active 精确模板、actor；独立只读回读按原幂等键和 actor 校验持久 Plan 修订，但固定 `current_admission_verified=false`，不得据此重发未知命令。
2. `services/aos-api/aos_api/ecommerce_business_investigation_aip_authority.py`：新增签名 BI 重绑定服务。输入只接原 prepare 幂等键、原 Plan ID、当前安装 ID/强 ETag、Plan expectedVersion、正式 Principal 与新幂等键；不接客户端模板正文/权限布尔值。单事务锁当前安装与 Plan head，核当前 persisted 成员/marking 权限、active 签名模板同安装、原 prepare Receipt 同 actor/租户/安装且 Plan 原修订/hash/template 精确一致；仅允许 draft head 仍是原准备修订、模板 resourceId/hash 相同而 revision 改为当前安装修订。重建原 Plan body，仅替换 templateRef，并由原 Store 复核六实例/治理依赖后写新 draft 与 Receipt。失败全部回滚，绝不冻结、配置、启 Host。
3. `services/aos-api/aos_api/routers/aip_production_contracts.py`：只为专用服务加请求和原有强 If-Match、Idempotency-Key 路由，再加 actor 范围的只读原 Receipt 路由；HTTP principal 不允许 body 传 actor/tenant/template。响应未知须先读 Receipt，不再次 POST。
4. `services/aos-api/tests/test_ecommerce_business_investigation_aip_authority.py` 与 `services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py`：先 RED 缺事务原语，再证正确顺序、同键重放/异体拒、错 actor/租户/安装/签名/ETag/Plan head/旧模板字节拒、回滚零 Receipt；Growth 1.13 与 1.12 原 signed 安装链复核。隔离链用直接插入的六 AgentInstance 仅作为前置测试数据，不充作当前正式实例或产品生产者证明。

## 风险与后续

- `FOR UPDATE` Plan head 与安装锁序需固定 Installation→Plan，避免与生命周期逆序；安装签名读者必须匹配已锁的 exact 安装，避免另一个同租户安装成为候选。
- 原 `aip_production_contract_receipt` 为不可变表且 runtime 角色无 UPDATE 权；只以普通 SELECT 核其不可变内容，不在该表使用需要更新权的行锁。隔离原链若检出权限错误，先按原权限模型修复 SQL，不加权限捷径。
- signed tree 与 Registry/signature 的重验由现有 `ActiveBIBusinessResolver` 完成；若它在嵌套连接中不能共享当前事务/锁，就先补无写的 transaction-aware 读者，不接受只凭早前 snapshot。
- 独立下一波才实现受控冻结，并以配置原 reader 同事务证明 frozen 当前 head。当前库只读、外部正式 OIDC/三身份/正式 trust/八配置/Owner 未齐时仅做隔离代码，不写当前实例，不启 Host/worker/Provider。

## 验收

原 signed active 安装与原 prepare Receipt 唯一对应、当前权限和 Plan CAS 均通过时，只产生新 draft 与一次原子 Receipt；任何漂移均无新 Plan/Receipt。通用 Plan 接口和旧 1.12 行为不变，页面继续禁入。本波 GREEN 不等于当前配置或首链完成。
