# AOS 桌面（`apps/desktop`）

> **状态**：TWC.1～6 ✅（同构 · 登录 · 托盘 · 深链 · 切区清缓存）  
> **详稿**：[20c](../../../docs/palantier/20_tech/20c-AOS桌面端详细技术方案.md) · [131](../../../docs/palantier/20_tech/131-TWC2-桌面同构主壳方案.md)～[135](../../../docs/palantier/20_tech/135-TWC6-桌面工作区切区清缓存方案.md)

## DoD

- [x] TWC.1～4  
- [x] TWC.5 `aos://` 白名单深链 · 未登录排队  
- [x] TWC.6 切区清 mp draft / ontology 本地缓存  
- [ ] TWC.7 Apollo 可收不少页（桌面展示策略）  

深链示例：`aos://open/workshop/inbox`

## 打包（macOS）

```bash
# 工具链 + 测试 + vite build（不生成 dmg）
bash ../../scripts/ci/pack-desktop-mac.sh --check

# 需 Rust / Xcode CLT：生成 bundle
bash ../../scripts/ci/pack-desktop-mac.sh --bundle
```

清单：[`scripts/pack/macos-desktop.md`](../../scripts/pack/macos-desktop.md) · [`scripts/pack/linux-desktop.md`](../../scripts/pack/linux-desktop.md) · 方案 [151](../../../docs/palantier/20_tech/151-macOS打包清单与pack脚本方案.md) / [152](../../../docs/palantier/20_tech/152-Linux打包清单与pack脚本方案.md)

```bash
# Linux 分轨
bash ../../scripts/ci/pack-desktop-linux.sh --check
```
