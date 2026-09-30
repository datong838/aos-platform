# W5CB4 BG00dh｜当前受检签名根接入职责 resolver 文件级方案（进行中）

## 上位与已读事实

231-2 要签名 manifest/artifact 原字节、确切安装 lock 和租户一致；BG00dg 已有 BI 严格 schema，但默认 `InstalledProductionProfileResolver` 读仓库 `bundles/releases/ecommerce`，那里没有当前 1.11.0。当前 `scripts/a0v_current_preview_http.py:preflight` 可核四包并返回 `signedRoot`；Host 的 `control_wiring._current_a0v_host_preflight` 已核 `AOS_BUNDLE_ROOT` 与该 signedRoot 相等，但仅返回 bool，未把受检根传给 AIP resolver。直接信任环境路径不可作为解决方案。

## 拟定最小接线与 RED

1. 先读取 `control_wiring._current_a0v_host_preflight`、`RuntimeHostSelection` 与 API 启动顺序，确定将已核 `signedRoot` 作为不可变进程内值传给 resolver 的最窄位置；所有路径 `resolve(strict=True)`，与报告/当前签名 receipt 同源，避免未启 Host 时由任意环境值静默替换。保持现有显式注入 `release_root` 测试接缝。
2. RED 覆盖：旧仓库 release 路径不覆盖当前签名根；任意 `AOS_BUNDLE_ROOT`、错 receipt/root、原位改写/路径换代、错 tenant/安装/lock/hash 均 fail closed；受检根的 exact artifact 才能解析。不得把测试 mirror 作为当前实例正向。
3. 最小实现后跑 resolver、Host 预检与 AIP 邻接回归，复审 root pin 的生命周期和异常回退。若发现需要改动当前数据库/签名包或跨进程密钥管理，停止该实例写入，继续独立代码项并另立安全波。

## 当前边界

本波尚未修改生产代码或启动 Host。当前签名包无 BI 模板，正式三身份/Host assignment/八配置均缺；即使 root 接线 GREEN，首链仍 pending。

## 2026-09-30 文件级设计复核

- `services/aos-api/aos_api/asset_registry/control_wiring.py`：仅在当前 Host 预检子进程返回签名 receipt、scope、数据库物理身份均通过后，调用进程内签名根 pin；失败继续返回 `False`。不改变 Host 选择返回类型，不传递任意环境路径作为权威。
- `services/aos-api/aos_api/aip_responsibility_template_authority.py`：默认 resolver 在当前签名运行模式必须从上述 pin 取根；未 pin、根目录代次漂移或旧根冲突均返回无制品。显式注入 `release_root` 的隔离测试接缝保留。读取每件制品时继续用当前安装、签名 Registry、精确 composition lock 与原始字节 SHA256 四道门。
- 复审补强：`AOS_BUNDLE_ROOT` 已配置即属签名源选择，缺 pin 或运行中 env 漂移一律拒绝；Registry 的 bundle/version 路径还必须留在受检根之下。
- `services/aos-api/tests/aip/test_aip_responsibility_template_authority.py` 与 `services/aos-api/tests/extension_runtime/test_production_runtime.py`：先做 RED，覆盖受检根正向、任意 env 不授权、未 pin 禁入、根换代/冲突禁入、错误租户与错误摘要，以及 Host 预检仅在全部条件通过后 pin。
- 只改上述两个生产文件与两个测试文件。当前数据库和签名树只读，不发布 BI 模板、不启 Host；若当前实例凭证仍缺，实际预检仍应 `SAFE_BLOCKED`。
