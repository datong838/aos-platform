# Linux · AOS 桌面打包清单（分轨）

> **真源方案**：[152](../../../docs/palantier/20_tech/152-Linux打包清单与pack脚本方案.md) · SOP：[24 §4.1](../../../docs/palantier/20_tech/24-AOS客户侧前置组件安装SOP.md)  
> **硬规则**：不改 Windows `*.ps1` / mac `pack-desktop-mac.sh`；MinIO / Dev Compose / Dev Keycloak **禁止**打进客户包。

## 1. 前置工具链

| 工具 | 验收 |
| --- | --- |
| Node ≥ 18 | `node -v` |
| npm | `npm -v` |
| Rust + cargo（真包） | `cargo -V` |
| 系统库（真包 · Debian/Ubuntu 示例） | `libwebkit2gtk-4.1-dev` · `libgtk-3-dev` · `librsvg2-dev` · `patchelf` · `libssl-dev` |

```bash
# Debian/Ubuntu 示例（需 sudo；客户自备）
sudo apt-get update
sudo apt-get install -y libwebkit2gtk-4.1-dev libgtk-3-dev librsvg2-dev patchelf libssl-dev
```

RHEL/Fedora 用发行版等价包名；**勿**把系统库打进 AOS 客户包。

## 2. 一键检查（不生成安装包）

```bash
cd aos-platform
bash scripts/ci/pack-desktop-linux.sh --check
```

覆盖：Node · ontology-sdk/web/desktop `npm test` · web `npm run build`（含 tsc）· desktop `vite build`。

## 3. 生成桌面产物（可选 · 需 Rust + GTK/WebKit）

```bash
bash scripts/ci/pack-desktop-linux.sh --bundle
```

产物通常在：`apps/desktop/src-tauri/target/release/bundle/`（deb/AppImage/rpm 视 Tauri 配置而定）。

## 4. 交付前核对

- [ ] 产品名「AOS 桌面」；本机平台不叫 Apollo  
- [ ] 渠道包 Base 指向客户环境  
- [ ] 验签更新（TWC.9）生产钥  
- [ ] 客户前置仍按 24（PG / 对象仓 / IdP 自装）

## 5. 生产 IdP 探针

```bash
bash scripts/ci/probe-prod-idp.sh --issuer … --jwks …
```

详：[60](../../../docs/palantier/20_tech/60-生产IdP联调手册.md)
