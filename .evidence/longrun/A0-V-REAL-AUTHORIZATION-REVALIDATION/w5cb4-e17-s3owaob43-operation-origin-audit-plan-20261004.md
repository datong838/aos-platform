# E17-s3o-w-ao-b43｜Capability operation 来源不可伪造审计计划

## 上位合同与避免重复施工

- 231-4/BIND-1 要求专用非 owner 发行、可信依赖快照、expected-version CAS 与同事务 Receipt。b25 `version-only evaluate` 伪造反例由 b26 的 test-only 行形状守卫拒绝；b27–b32 已独立补双 Receipt、非法列、CREATE 初态、published Catalog 精确来源与 Receipt source revision。不能重做这些既有隔离测试并误报为新完成。
- 当前 `test_e17_s3owaob22_capability_receipt_identity_pg.py` 的 test-only issuer 正向 `evaluate` 直接以任意 `dependency_snapshot_hash='b'*64` 和本机时间更新行并插 Receipt，未调用 `AipBindingReadinessService` 的正式依赖读取；这说明行形状/issuer 登录仍不足以证明业务来源。当前正式 issuer 角色/OIDC 0、Capability active Binding0，真实库只读135。

## 文件级步骤

1. 只读核原 `AipCapabilityBindingService.evaluate` 的计算、issuer 事务边界和 b22 test-only 守卫正向段；列出客户端/DB 可伪造字段与真正应由当前独立 Reader 决定的字段。聚焦 `services/aos-api/aos_api/aip_capability_binding_service.py` 与 `services/aos-api/tests/aip/test_e17_s3owaob22_capability_receipt_identity_pg.py`，不大改。
2. 串行运行现有完整 schema 的 b22 test-only 正反合同及相邻能力测试，证明正向 `evaluate` 的任意 hash 仍可持久并有 Receipt；明确这是**缺口证明**而非业务正向。若测试失败先诊断环境/真实依赖，不使用 mock 或当前库写。
3. 本波只登记事实与下一代码切片设计：正式 issuer 必须只由受控命令调用，其 `evaluate` 结果要在同一最终事务内绑定当前签名来源、依赖 hash、时间与 Receipt；单靠可写 GUC、行差异或私有 DB 登录都不足。没有可验证来源前保留 xfail、不给当前库发行迁移。下一波可先做“精确来源快照与最终事务重算”的独立 RED/最小代码，不碰当前实例授权缺口。

## 边界

- 不改生产代码/真实库、不启 Host/worker/Provider、不用测试 issuer 冒充正式身份；org-org/dev-project 唯一正向、dev-org 零副作用。不读商城源、不回放旧12 Run、不手工 run_definition、不碰230 L0、不 push。每日提醒每次到达另做最新完整重启。
