# BM 运行时凭据恢复与直系后继激活验证（2026-09-20）

## 结论

`BM_CREDENTIAL_ROTATION_GREEN_BUT_PREPARATION_FAILED_ALIAS_MISMATCH`。

三平面凭据已按正式受控路径恢复并真实连通；BM 已从 exact BL detach authority 创建为全新 approved installation。但 BM 首个 runtime-apply 在读取已验证 runtime artifact 时正式失败，失败码 `PREPARATION_EXECUTION_FAILED`。该 operation 已终结且三资源 released，Host 已自行停止。未重发 prepare，未进入 verify/stage/configure/enable/register/cutover。

## 1. 凭据恢复

- 固定角色：`aos_a0v_web_20260912`、`aos_a0v_runtime_20260912`、`aos_a0v_directory_20260912`。
- 三角色均 login、非 superuser、非 bypassrls；membership 分别为 web 无继承、runtime 仅 `aos_runtime`、directory 仅 `aos_extension_directory`。
- host identity `a0v-local-ecommerce-host-20260912` revision 1 enabled，正租户 assignment revision 1 assigned，canary assignment 0。
- 备份：`aos_meta_head-pre-bm-credential-rotation.dump`，10993910 bytes，hash `sha256:a9ec078ab7d15007de68b1f98271099b228b64b9454411b003f36808f88f3fa3`。
- 新 credential file 为仓库外 `0600`，hash `sha256:9af9eca92c395cbc1521a6668429a76001addcc22a086a833754feb8ca9a3b7d`；三个 DSN 均逐一真实连接成功，未输出 secret。

## 2. BM create

- exact predecessor：BL `ac9b3ec8-68ad-4e05-9f30-b2f8f6a473bc` / generation `116d12fc-93bc-4071-a973-fdc6830ea8b1`，legacy rev164/group191，definition rev118 disabled，detach Receipt 与 released 资源均通过 preflight。
- BM installation：`370d4287-3402-40bb-b3da-d479633da7c4`，approved rev3。
- composition `cbc444da-73ec-4694-824e-39462b5c534a`，lock `sha256:1c38348fc14e86356c352a41a157f0bc89c1eb9e8a5b4fd32e2f1f3bdbc20b42`。
- resolved：core 1.4.1、niushop 1.23.1、growth 1.10.1、operations-base 1.2.1；31 contributions、8 modules。
- 创建前 Runtime Host=0、18181=0、snapshot worker=0；随后只启动一个正式 Host，第二 Host=0。

## 3. 正式失败与根因

- runtime-apply operation：`391bc3e3-ccc9-40c4-9f08-3f36686d882d`。
- 最终状态：`failed / preparing / PREPARATION_EXECUTION_FAILED`，revision 7。
- 三个 runtime resource lease 均 `released / observed_release=true`。
- Host fail-closed 终止，安全错误链指向 `CurrentRuntimeReleaseArtifacts.read_artifact -> ManifestLoader.read_verified_artifact` 的 `ManifestInvalidError`。
- 确定性根因：本波 registry publication 把 artifact refs 持久化为 `bundle://a0v-bm-recovery/...`；生产 wiring 对 `AOS_BUNDLE_ROOT` 只允许 `server` 与历史契约 `a0v-canonical` 两个 alias，因此 runtime loader 正确拒绝未 allowlist 的 `a0v-bm-recovery`。
- 这不是 transient、Host 数量或凭据故障；禁止重发同一 prepare。正确恢复路径是以标准 `a0v-canonical` alias 发布下一组不可变补丁坐标，再正式退休该失败 BM，创建 direct successor BN。

## 4. 代码与测试

- canonical installer 仅新增向后兼容 `operations_version="1.2.0"` 参数；既有调用默认行为不变。
- BM wrapper 指向新 trust/signed/credential material，并使用四个补丁坐标。
- 初始专项与 canonical 回归：`16 passed`；切换独立不可变 activation state 后专项：`5 passed`。
- 未修改共享 runtime allowlist；未把错误 alias 追加为生产信任入口。

## 5. 安全边界读回

- BM execution attempt：0 total / 0 running；未创建 binding，未进入业务执行。
- `ecom_link=0`、projection pending=0、canary installation=0。
- AOS Runtime Host=0、18181=0；未启动 cron/snapshot worker；未调用 `run_definition`；未读取商城源数据；230 L0 保持挂起。
- 失败边界明确、无未知提交，不需要人工决策。

## 6. 下一波

自动进入 **BN canonical-alias registry repair + failed BM retirement + direct successor**：先 plan；将 registry recovery publisher 固定为 `a0v-canonical` 并发布下一组不可变 patch versions，qualification 后精确读回 artifact refs；再按正式 failed-preparation retirement 路径退休 BM，最后从 exact detach authority 创建 BN。任何历史版本不覆盖、不删除。
