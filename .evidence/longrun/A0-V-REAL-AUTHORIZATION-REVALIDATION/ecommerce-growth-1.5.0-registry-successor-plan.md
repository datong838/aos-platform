# Ecommerce growth 1.5.0 Registry successor 方案

日期：2026-09-12

## 当前真值与断点

`solution.ecommerce.growth@1.5.0` 已通过隔离 OCI build/qualification，但 qualification 使用的临时密钥没有持久化，不能作为 Registry 发布密钥。当前隔离恢复库中四个 canonical 版本均为 `published`，其中 growth 仍是 1.4.0；它们的 artifactRef 全部使用 `bundle://a0v-canonical/...`。

首装状态目录仍保存权限为 `0600` 的 Ed25519 私钥与 trust-root 文档，以及 `signed-bundles-v4`。这组密钥是现有发布记录的持久信任根，successor 必须复用并验证字节身份，不生成新密钥，不输出私钥内容。

生产 `control_wiring._allowlist_roots` 当前只提供 `catalog` 和条件式 `server` alias，项目 `.env` 也没有 `AOS_BUNDLE_ROOT`、`AOS_BUNDLE_TRUST_ROOTS_FILE` 与 `AOS_EXTENSION_RUNTIME_PLATFORM`。因此重启后的生产 reader 无法解析已存的 `a0v-canonical` artifactRef；Registry 与 Installation 真值存在，但 signed artifact 读取会 fail closed。

旧 `a0v_canonical_ecommerce_first_install.py` 固定描述 v4 首装，但它动态导入的构建器已经指向 1.5.0。不得重跑或修改这份历史首装脚本来完成 successor，以免把首次安装 Receipt 与升级发布混为一体。

## 最小实施方案

1. 在 `control_wiring._allowlist_roots` 中，仅当 `AOS_BUNDLE_ROOT` 明确存在时，把同一个 server-owned root 同时绑定为 `server` 和历史兼容 alias `a0v-canonical`。两者没有额外目录权限；未配置 root 时两个 alias 都不存在并继续 fail closed。
2. 新增单用途 successor 脚本。默认只做 preflight；`--apply` 必须显式锁定 `colima-aos-extension / aos-a0v-recovery-pg / aos_meta_head`，并读取 exact OCI build/qualification Receipt、现有持久 key/trust-root 和 Registry 1.4 真值。
3. 创建 `signed-bundles-v5` 时先复制不可变 v4 signed tree，再叠加本次仓外 build 输出。只为 builder 当前四包补签名，因此保留 growth 1.4.0 并新增 1.5.0；随后用同一 trust-root 验证五个 canonical coordinate。已存在 v5 时必须逐字节/内容身份相符，否则阻断。
4. 1.5.0 通过 `RegistryService` 走 create_version → validate → publish。actor、roles、publisher scope 明确固定；若版本已存在，只接受 manifest/content/artifact 完全一致并按当前状态续跑。发布前备份数据库，结果记录 mutation count；重放必须为零 mutation。
5. 脚本不创建或升级 Installation，不启动 OCI，不调用 Provider，不产生外部发布。Registry 成功后再单独形成 Composition/Installation successor 方案。
6. 将三项非秘密运行配置写入项目 `.env`：`AOS_BUNDLE_ROOT=<signed-bundles-v5>`、`AOS_BUNDLE_TRUST_ROOTS_FILE=<persistent trust-roots.json>`、`AOS_EXTENSION_RUNTIME_PLATFORM=linux/arm64`。写入前检查同名键，已有不同值时阻断；配置文件不纳入 Git。

## 修改范围

- `services/aos-api/aos_api/asset_registry/control_wiring.py`
- `services/aos-api/tests/asset_registry/test_control_wiring.py`
- `scripts/a0v_ecommerce_growth_1_5_registry_successor.py`
- `services/aos-api/tests/extension_runtime/test_a0v_ecommerce_growth_1_5_registry_successor.py`
- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/`
- `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/closure-manifest.md`

## 退出条件与回滚边界

单测覆盖 alias 的配置/未配置边界、v4 保留、1.5 签名、漂移阻断和 Registry 幂等重放；apply 与 replay 都生成独立 Receipt。发布后 1.4.0 字节与 Registry 记录保持不变，1.5.0 唯一 published，正负租户 Installation 均无变化，四类业务副作用为零。

若发布后尚未升级 Installation，不需要撤销 published 历史版本；运行配置可恢复原 `.env` 备份，v5 tree 可保留为审计制品。任何未知数据库结果都停止并先只读核验，禁止盲目重发。
