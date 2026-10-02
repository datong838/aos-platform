# E17-a1｜当前安装发行证据只读读者（正式启动前置切片）

## 上位与现状

承接 `w5cb4-e17-formal-startup-owner-plan-20261002.md` 和 231-2/231-3。当前预览 `preflight` 写死四版本/binding0，不能作为 Growth1.13 正式发行视图。现有 `load_stored_lock`、`RuntimeReleaseRevalidator`、`ManifestLoader` 已分别校验原安装锁、当前 Registry/ReleasePolicy、已签名原字节。先组合这些**原权威读者**，不新造签名权威；本切片输出只读 evidence，固定 `EVIDENCE_ONLY_NO_START`，绝不接 API/Host 启动。

## 文件级改动

1. `services/aos-api/aos_api/extension_runtime/current_installation_release_evidence.py`：由 caller 传明确 `TenantScope`、UUID 安装、连接工厂、正式由部署方提供的 `ReleasePolicy` 和 `ManifestLoader`。函数自开 `REPEATABLE READ READ ONLY` 事务、应用原租户范围；以安装当前 revision/ETag 联原 revision 与 composition，要求唯一、state 为 approved/applied/active、精确 lock PK/hash；复用 `load_stored_lock` 和 `RuntimeReleaseRevalidator`，再以同事务 Registry snapshot 和 ManifestLoader 重验每个 selected 的 publisher/id/version/content hash、manifest、signature 与唯一 source。返回不可变简要证据：scope、安装/current+active revision/ETag、lock hash、selected 精确 identity/hash、runtime member 与数据库时间，授权字面值只能为 `EVIDENCE_ONLY_NO_START`。缺/错租户、过期/撤销签名、错锁、字节漂移、重复或非当前 release 均失败关闭。此读者**不**验证 OCI 实际镜像、Host Owner、八配置、身份、预算，也不启动任何服务。
2. `services/aos-api/tests/extension_runtime/test_current_installation_release_evidence.py`：RED 先证明函数不存在；随后以当前权威库只读及当前预览签名四包检验实际安装的证据视图和 dev-org 缺安装拒绝。此测试仅证明可复用读者，不把预览信任根提升为正式授权。另用读者的返回类型/错误码断言绝无 `ready`/`enabled` 启动许可。

## 验证与风险

专项只读 PG、相邻 ReleasePolicy/安装锁/当前预览测试、`py_compile`、`git diff --check`；源码复审确认未加真实库写路径、未绕旧 pinned 预览、未改 Host。当前预览签名仅作真实字节读者验收；Growth1.13 正式信任根和 OCI/Owner 仍是下一切片，不能称当前实例可正式启动。浏览器维持原禁入状态并只读回看。
