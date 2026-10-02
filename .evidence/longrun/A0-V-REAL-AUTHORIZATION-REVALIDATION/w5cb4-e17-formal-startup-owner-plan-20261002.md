# E17｜正式版本感知启动预检与精确 Host Owner 文件级方案

## 当前事实与合同

起点 `m1@f8b6b983`、Authority `AOS-001141`。231-2 要求受信 Registry release、不可变签名字节、当前 trust root/撤销状态、exact lock、OCI digest/安全 profile；231-3 要求原 Installation lifecycle/强 ETag/幂等 Receipt、同代 ready binding、fence/epoch/权限/预算/策略消费时重验。E17 当前实例要求外部 OIDC、独立 API 与 Directory/Runtime/Web 身份、Host assignment/identity、八配置、精确 Owner。当前代码/库 `a0v_135`，本机预览 API/Web 与权威卷完整重启 GREEN，但八配置/assignment/identity/binding、Growth1.13 当前正式发布仍0，Host/worker关闭。

新鲜负例（只读，不启动）：`scripts/a0v_current_preview_http.py --serve-limited --api-identity-file /nonexistent/identity.json` 退出2 `EXTERNAL_OIDC_CONFIG_REQUIRED`；`scripts/a0v_current_runtime_host_preflight.py` 不给 credential file 退出2 `CREDENTIAL_FILE_REQUIRED`。受限 API 和 Host 都在当前 `preflight` 里要求 pinned 四版本且 binding0；独立 Host 启动器预检后仍固定 `FORMAL_OWNER_AUTHORITY_UNPROVEN`。这些门保证当前实例禁入；不能删门或用 test-only 凭据跨过。

## 实现顺序与精确文件

1. **正式签名发行视图读者**：在 `scripts/a0v_current_preview_http.py` 旁增加独立正式模式的只读预检，复用 `aos_api.asset_registry` 既有 Registry release/ReleasePolicy、ManifestLoader、current Installation exact composition lock 校验。输出只允许包含 scope、installation ID/current+active revision、lock hash、签名指纹、Growth1.13 exact bundle/version/content hash、OCI image digest、schema head和证据代次；任何缺行、多行、旧代、撤销、错租户、错签名、错摘要拒绝。旧 `preflight` 与 `--serve` 的 pinned 四版本/零绑定断言保持原样。不得把本地 `sign_ecommerce_growth_1_13_candidates.py` 的 key/trust 自动提升为正式源。
2. **受限 API 启动选择**：仍在 `scripts/a0v_current_preview_http.py`，`--serve-limited` 保持 HTTPS 外部 OIDC、受保护 API identity 文件和无 dev auth；只在正式签名发行视图成功后启动，服务端 `AOS_BUNDLE_ROOT/TRUST_ROOTS` 来自该视图。当前缺正式签名/安装材料时失败关闭，不能回退旧预览视图。原 `--serve` 不动。
3. **Host 三身份与八配置**：`scripts/a0v_current_runtime_host_preflight.py` 接正式发行视图并重验 Directory/Runtime/Web 三个独立角色、同库/OID、assignment/identity、八类当前配置与绑定安装代次；测试 `services/aos-api/tests/extension_runtime/test_a0v_current_runtime_host_preflight.py`。准备模式仍不能豁免身份/assignment；Full 模式缺任一配置拒绝。
4. **精确生命周期 Owner**：`scripts/a0v_ecommerce_runtime_host.py` 在正式 preflight 与 Runtime 选择之前，以原 231-3 lifecycle/Receipt/同代 binding/tenant/epoch/fence 组合一个只读 Owner 证明；每次启动重读且按数据库时间与凭据 generation 核。仅当 Owner fully ready 才替换固定 `FORMAL_OWNER_AUTHORITY_UNPROVEN`；缺/撤销/错代/跨租户/未知提交均保持禁入。测试 `test_a0v_ecommerce_runtime_host.py` 和隔离 PG 的原 lifecycle 联合用例。未有合法来源前不启本机 Host。

## RED/验证与部署边界

- 首个 RED：Growth1.13 正式发布+同代 binding/签名/OCI 完整的可销毁 PG 应通过正式视图；现代码走 pinned 预览会 `PREVIEW_DATABASE_DRIFT`。并做缺当前签名、错 OCI、错 lock、跨租户、revoked、安装 approved 但未 active、旧 generation/epoch、缺八配置、无独立身份的拒绝。正例须由真实 Registry/安装/lifecycle producer 建立，不直接插入一份伪状态；测试通过仅证明代码，不代表当前实例通过。
- 相邻回归：三份现有启动/Host 测试、ReleasePolicy/安装 lifecycle/三身份 PG 测试；`py_compile`、`git diff --check`，适用时浏览器八工作台和禁入回读。首条业务链还需正式 Owner、Receipt 与自然调度/回执独立证明。
- 当前真实库仍只读。若要正式发布/切换，另波做当日独立一致备份、隔离全库恢复和新旧启动器双向演练、零执行窗口、当前授权/配置来源对账；未知结果只读对账。API 正式模式未过不替换现行质量预览进程；Host/worker/Provider 不启动。回滚为停正式进程、禁入并恢复旧 pinned 预览，不删除卷/备份。

## 下一安全动作

先检查既有正式 Registry/安装/lock 读者可复用接口与外部身份材料是否齐备。若正式信任根/OIDC/凭据仍缺，当前实例维持禁入；转做已登记的 BG00gw d2b3c4g2 原持久 Review Receipt 与内容生产者的独立 RED/最小代码，不以新 plan 或 API200 宣称首链。
