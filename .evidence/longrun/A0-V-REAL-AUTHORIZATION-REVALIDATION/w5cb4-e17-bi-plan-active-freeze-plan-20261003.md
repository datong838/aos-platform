# W5CB4 E17｜签名 BI Plan active 后受控冻结文件级方案

## 上位与现状

- 231-3 的配置 `roleRefs` 只接当前 frozen Plan exact ref；`read_current_responsibility_plan_ref` 锁当前 head、验 revision/hash/结构化列与 lifecycle，返回布尔值，不授运行许可。
- 551 已有 `bi_responsibility_plan.rebind`：approved 原 prepare Receipt→active 签名安装→新 draft/Receipt；未知结果只读回读。通用 `freeze_responsibility_plan` 只核 Plan 自身依赖，不核原 rebind Receipt 或当前签名安装，不能直接当 E17 正式冻结入口。
- 当前正式三身份、Growth1.13 正式签发、八配置与 Host Owner 缺失；此波只在隔离原签名链实施，不写当前库、不启 Host/worker/Provider。

## 目标与文件

1. `aos_api/aip_production_contract_store.py`：把原 Plan freeze 提取为调用方持有事务的原语，保留普通路由 operation/hash/回放；专用 operation `bi_responsibility_plan.freeze` 的 Receipt 绑定 rebind Receipt ID、active 安装/ETag、冻结前 Plan exact ref、actor。成功仅新 frozen revision/Receipt，同事务失败零写。新增按原键和 actor 的只读回读，固定 `currentAdmissionVerified=false`。
2. `aos_api/ecommerce_business_investigation_aip_authority.py`：专用受控冻结服务锁 Installation→Plan head；核正式 OIDC/当前成员和配置权限、当前 active signed Registry/模板、原 rebind Receipt 同 tenant/actor/Plan/安装/旧新 exact ref、当前 draft head/version/hash；再用原 Store 复核 readiness/六实例依赖，调用事务原语。提交前重读签名源，并以 `read_current_responsibility_plan_ref` 在同事务核新 frozen revision；不把该 reader 的 True 解释为整体配置成功。
3. `routers/aip_production_contracts.py`：专用 POST 要求强 Installation If-Match、Plan expectedVersion、原 rebind 幂等键与新 Idempotency-Key；GET 只读 Receipt。请求不接模板正文、actor/tenant、权限标志。
4. `tests/test_ecommerce_business_investigation_aip_authority.py`、`tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py`：RED 缺受控事务原语；Growth1.13/1.12 原安装链正向及同键重放、异体冲突、错误原 Receipt/actor/租户/ETag、Plan head、签名撤销、readiness 失败和零残留负向。普通 freeze 相邻回归、浏览器禁入复核。

## 审查边界

- 锁序 Installation→Registry version→Plan head；Receipt 不加需要 UPDATE 权的行锁。签名文件读者与 Registry 行锁并行复核，提交前二次校验；若 transaction-aware 共享读缺失，保持实例失败关闭。
- 冻结只产生一个配置源候选，不填其余七类、不授权配置提交或 Host。Receipt 对账不触发重发；原 12 Run、商城源、dev-org、230 L0 不碰。

## RED 后的分层执行（2026-10-03 00:30 CST）

原 Growth1.13 signed 全链首次调用受控冻结，在原 Store readiness gate 因六个 `SKILL_BINDING_NOT_ACTIVE` 失败；这六个 Skill 的正式发布/绑定生产者不是本波安装链的一部分。不得为本波直接插入 active SkillBinding、用 mock readiness、放宽冻结规则或把该 RED 说成正向冻结。本波先完成内部受控冻结的联锁与失败关闭验证：缺绑定、错原 Receipt/ETag/actor/tenant 时 Plan head 和冻结 Receipt 均不变；不暴露 POST/GET HTTP 入口，不声称冻结成功。后续独立波先接原 Skill 发布、CapabilityBinding 与 AgentInstance 绑定来源，形成可复核的当前 signed Skill 依赖，再恢复正向冻结与只读 Receipt/公开接口测试。
