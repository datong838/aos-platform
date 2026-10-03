# s3o-w-u 第一切片｜BI 发行命令与身份重验验证

- 基线 AOS `m1@1c5f6742`、Authority `AOS-001233`、当前真实库 `a0v_135` 只读。依据 231-3/231-9、618 接续和本波文件级方案。
- RED：新增 BI issuer 命令/认证测试后收集报 `ModuleNotFoundError`，exit2。初版 GREEN 尝试复用 `AipContractModel` 别名时发现 `expectedEtagVersion` 与现有强 ETag 语义 `expectedETagVersion` 不同，12 failed；修正显式别名以及原 rebind `prepareIdempotencyKey`。再次新增无效 bearer 错误脱敏断言，复现 Pydantic `ValidationError` 暴露 `input_value='header.payload.signature.extra'`，exit1；命令模型仅设置 `hide_input_in_errors=True` 后修复。
- 最终新增 `BIIssuerPrepareCommand`/`BIIssuerRebindCommand`：schema1、规范安装 UUID、精确租户/幂等键、严格正整数 ETag/Plan 版本、原 rebind Plan 与准备 Receipt 引用，拒额外 actor/权限字段；bearer 以 `SecretStr` 保存且错误文本不回显非法输入。
- `authenticate_bi_issuer_request` 对每个命令调用现有外部 HTTPS OIDC 配置门和 `resolve_principal`，核验 token_kind、claims/命令双租户及有效主体；不接 API 自报 Principal。测试覆盖无配置/开发开关、dev 签名 JWT、错租户、非 OIDC、空主体、prepare/rebind 重验。
- 专项加相邻 network issuer contract/auth 与 BI HTTP 测试 `82 passed`、exit0；`py_compile`、`git diff --check` exit0。代码只新增两个命令/认证模块和两份测试，不改公开 HTTP 默认 503、不连接当前数据库、不创建 issuer 进程/凭据/角色，不启 Host/worker/Provider。
- 方案一致性与风险：身份重验入口只证明纯代码校验，不证明正式 IdP、内核 peer、独立 UID、DB `session_user`/ACL、durable attempt 或 Plan/Receipt 当前正向。下一波须在隔离环境接受控私有 IPC 和受限发行服务，未知结果只读 Receipt 对账；正式迁移/当前库切换仍要全备、全 schema 克隆、恢复演练、零执行窗口。
