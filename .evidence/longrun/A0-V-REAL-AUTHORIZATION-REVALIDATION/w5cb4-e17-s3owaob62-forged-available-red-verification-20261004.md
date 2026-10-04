# b62｜普通 issuer 伪造 available 的隔离 RED

## 边界与复审

- m1 `1b0e4185` 仅修改 test-only Capability Receipt 克隆测试及文件级计划；生产服务/迁移/当前卷未改。测试函数先验证 DB 名为 `aos_test_*_ti4_test`，再建随机非 owner 登录、RLS/ACL，`finally` 清理角色与临时对象。
- 上位 231-3、BIND-1 要求当前签名来源、exact 依赖和最终事务复核；b46–b50 的 blocked/锁序不能授权 available。新增 `require_trusted_available` strict xfail 让普通 issuer 写 `operational_readiness='available'`、自造 64 位 hash、时间窗及 evaluate Receipt，并要求数据库拒绝。实际没有抛 `InsufficientPrivilege`，说明缺口未关闭。

## 本次命令与结果

| 命令 | 结果 |
| --- | --- |
| `AOS_DOTENV_DISABLED=1 uv run pytest -q -rx --tb=short --disable-warnings tests/aip/test_e17_s3owaob22_capability_receipt_identity_pg.py -k require_trusted_available`（`services/aos-api`） | exit0；1 xfailed/3 deselected，严格预期失败原因是 `available snapshot and Receipt can be forged without current signed dependencies`。这不是 GREEN。 |
| `AOS_DOTENV_DISABLED=1 uv run pytest -q -rx --tb=short --disable-warnings tests/aip/test_e17_s3owaob22_capability_receipt_identity_pg.py tests/aip/test_aip_binding_readiness_service.py` | exit0；21 passed/5 xfailed。原 blocked 正向、原可信来源 xfail 与 active 最终事务 xfail 保留。 |
| `python3 -m py_compile services/aos-api/tests/aip/test_e17_s3owaob22_capability_receipt_identity_pg.py && git diff --check` | exit0。 |

## 结论和下一波

- b62 只将可伪造 available 的精确失败固定为隔离 RED。普通 issuer 当前能制造看似有效的 evaluate Receipt；不能因它的外形或当前签名安装只读 Reader 就激活 CapabilityBinding/Host。
- b63 继续唯一136合同前的可信 evaluator 设计与受限命令：同最终事务锁签名 Installation/Registry，计算/核验八类当前依赖，CAS Binding＋唯一 Receipt，普通 issuer 无直接 evaluate DML；先独立负门/正门与锁并发，再讨论唯一迁移。当前真实库只读，正式凭证/角色、Growth1.13 active、八配置/六 Binding 和自然首链均未证明。
