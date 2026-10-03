# E17-s3o-w-ao-b16｜正式 Reader/issuer 来源与克隆切换文件级方案

## 方案复习与已知事实

- 231-4、AIP-7 22、BIND-1 31 要求同库双身份、Reader 与发行者各自非 owner、私有凭据、租户 RLS、外部 OIDC；b15 新全备在独立库完整恢复，26表 count/hash 相等。b3 只在另一个 test-only 恢复库验证了 Reader apply，不是本次正式切换。
- `services/aos-api/aos_api/routers/aip_bindings.py` 只在 Reader/issuer 两组 `AOS_AIP_BINDING_*` 配置完整、同库、不同私有文件时接线；当前 `.env` 有效键名为0。`scripts/a0v_current_preview_http.py --serve-limited` 另要求 HTTPS 外部 OIDC、API 独立非 owner 身份文件和可连真实库的私有 passfile；仓外现有 API 文件名标 `testonly`，不可接当前。
- `aip_registry_issuer_connection.py` 的 capability lifecycle 身份门要求运行角色对共享 RegistryReceipt 无 INSERT；当前原库该 INSERT 仍有合法业务依赖，b8/b12 已证明不能简单全局撤销。正式 operation scoped 发行合同尚未冻结。b15 恢复库不应通过宽权捷径制造假 GREEN。

## 本波步骤与退出门

1. 仅核 key 名、文件路径/权限/标记和预检 reason code，不读密钥内容；核角色/ACL/Owner/外部 OIDC 来源。若只有 test-only 或无来源，给出精确缺口，实例禁入。
2. 以 b15 新恢复库执行只读 catalog 与拟用 Reader/issuer 协议前置检查；任何克隆 DDL 先确认它与原卷隔离、私有凭据生成/归属及事务回滚可证明。沿用 b3 已通过的 Reader 同形状链，集中检查 issuer 共享 Receipt ACL 与 exact operation 的冲突，不重复造空态通过。
   - 发现 b15 恢复使用 `--no-acl`，因此先对比原库/恢复库的 Receipt ACL；若不同，克隆上的 issuer 正向结果不得外推到原库，后续必须有角色/ACL 同形状复演或显式负门。
3. 仅当正式来源、operation scoped Receipt 合同、OIDC 与零执行窗口齐备，另立当前库迁移波。当前库只读，API/Host/worker/Provider不切换；可独立推进八配置/绑定代码，不把局部缺权升级为整个 Goal blocked。

验证要求：每条命令及 exit code、当前与恢复库身份、错误码、未发生外部副作用、方案/代码一致性在 verification 落盘；如无新增代码，测试门按实际只读证据判定，不把重复历史测试计作本波 GREEN。完成后精确 m1 提交与 AOS/Prime、D-waves 同步。
