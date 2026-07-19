# macOS · AOS 桌面打包清单（分轨）

> **真源方案**：[151](../../../docs/palantier/20_tech/151-macOS打包清单与pack脚本方案.md) · SOP：[24 §4.1](../../../docs/palantier/20_tech/24-AOS客户侧前置组件安装SOP.md)  
> **硬规则**：不改 Windows `*.ps1`；MinIO / Dev Compose / Dev Keycloak **禁止**打进客户包。

## 1. 前置工具链

| 工具 | 验收 |
| --- | --- |
| Node ≥ 18 | `node -v` |
| npm | `npm -v` |
| Rust + cargo（真包需要） | `cargo -V` · `rustc -V` |
| Xcode CLT（真包需要） | `xcode-select -p` |
| （可选）Tauri CLI | `npm run tauri -- --help`（在 `apps/desktop`） |

无 sudo 时工具链见 24 §4.2。

## 2. 一键检查（不生成安装包）

```bash
cd aos-platform
bash scripts/ci/pack-desktop-mac.sh --check
```

覆盖：Node · ontology-sdk/web/desktop `npm test` · web `npm run build`（含 tsc）· desktop `vite build`。

## 3. 生成桌面产物（可选 · 需 Rust）

```bash
cd aos-platform
bash scripts/ci/pack-desktop-mac.sh --bundle
```

产物通常在：`apps/desktop/src-tauri/target/release/bundle/`（dmg / app）。

## 4. 交付前核对

- [ ] 产品名「AOS 桌面」；本机平台文案不叫 Apollo  
- [ ] 渠道包 `channel.*.json` 若预置 Base，确认目标环境  
- [ ] 签名更新（TWC.9）：生产分发须验签；Dev 可用自签  
- [ ] SBOM / AGPL 门禁：沿用 `scripts/ci/check-sbom-gate.ps1`（Win CI）；mac 本机可后补 syft  
- [ ] 客户前置仍按 24：PG / 对象仓 / IdP **客户自装**

## 5. 生产 IdP 探针（分轨）

```bash
# 并列 Windows：scripts/ci/probe-prod-idp.ps1
export AOS_OIDC_ISSUER=https://idp.example/realms/aos
export AOS_OIDC_JWKS_URL=https://idp.example/realms/aos/protocol/openid-connect/certs
bash scripts/ci/probe-prod-idp.sh
```

详：[60](../../../docs/palantier/20_tech/60-生产IdP联调手册.md)
