# E17-s3o-w-ao-b1｜CapabilityBinding 独立 Reader/issuer 生产组合验证

## 范围与依据

- 先读 231-4、AIP-7 22、BIND-1 31、D-waves 2026-10-04 与 `w5cb4-e17-s3owao-formal-reader-production-wiring-plan-20261004.md`；编码前在该计划追加本切片文件级步骤。
- 仅改 `services/aos-api/aos_api/routers/aip_bindings.py` 与 `services/aos-api/tests/aip/test_aip_binding_api.py`。当前真实库零写；未建角色、未改 ACL、未读取商城源、未启动 Host/worker/Provider。

## RED / 最小实现 / 回归

1. 新增生产组合入口测试后，`uv run pytest -q tests/aip/test_aip_binding_api.py -k capability_private_identity_configuration`：ImportError（`build_capability_binding_service` 缺失），退出码2，已复现。
2. 最小实现：两组环境配置各需 host/port/database/passfile 全字段，必须同一精确库与不同私有文件；配置缺项、错库或同一 inode 凭据文件失败关闭。无配置沿用 preview/active 禁入；完整配置下 issuer 为 `capability_lifecycle` 独立工厂，Reader 同时注入事实 authority 与全部模型子读者。连接时仍由原工厂校验正式登录角色、ACL、FORCE RLS、只读事务和租户。
3. `uv run pytest -q` 六个相邻文件（`test_aip_binding_api.py`、`test_aip_binding_readiness_service.py`、`test_e17_s3oo_capability_reader_pg.py`、`test_e17_s3ol_capability_issuer_pg.py`、`test_aip6_capability_run_handoff.py`、`test_aip_agent_registry_store.py`）：49 passed/8 warnings，退出码0。两文件 `py_compile` 退出0，目标 `git diff --check` 退出0。

## 复审与未完成门

- 组合只在两组私有配置完整时建立，不打开连接，不隐式创建角色或更改当前数据。当前正式 Reader/issuer role 均未切换；OIDC、Owner、八配置、六 Binding 和自然首链仍 pending。没有当前正式凭据的正向证明，测试 GREEN 仅证明接线与失败关闭。
- 模块级服务在 API 进程启动时读取配置，后续私有配置变更需要受控重启 API。当前预览进程仍使用 `AOS_AUTH_ALLOW_DEV` 路径；本切片不把它解释为正式受限 API。当前默认服务的其他读/创建路径不在本切片改动，正式部署仍须单独核 issuer 全路径和 OIDC。
- 下一步：按 s3o-w-ao-b 对维护 runner、完整恢复克隆及正式 Reader/issuer 角色切换分门推进；任何当前库写入前取新一致备份、独立全库恢复并取得零执行窗口。Host/worker/Provider 保持关闭。
