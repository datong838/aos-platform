# W5CB4 当前源码新实例 Composition/Installation 子波计划（2026-09-27）

- 上位边界：当前新库 `aos_current_preview_20260927@a0v_106` 已有四个 exact PUBLISHED release（`m1@74fd1865`），Installation=0；签名根位于仓库外。复习 canonical 首装的无 baseline 四节点/三边、maker/checker exact hash 门，Runtime 配置前不得声称 active。
- 文件级：仅给 `scripts/a0v_canonical_ecommerce_first_install.py` 的复用函数增加可选当前 trust path、overlay/display、actor 参数，默认值保持旧首装行为；新增 `scripts/a0v_current_preview_installation.py` 和对应专项测试。本计划与 verification 落证据目录。
- 默认只读 preflight：校验目标 DB/HEAD、四个 published exact 版本、零现有安装、签名 Receipt 与 Registry 内容对应。显式 apply 前在外置新 state 写 intent；调用正式 CompositionService/InstallationService，maker 创建/提交、不同 checker 精确批准，独立回读四 resolved、三依赖、八 UI、唯一 approved installation。未知部分结果先冻结/对账，不重发。
- 不启 Runtime operation/binding/Host，不切 8080/8434；若当前 ResponsibilityPlan/RuntimePolicy/配置/预算权威缺失，则保持 approved 并列下一子波缺口。专项、邻接、方案/代码复审、verification、m1 精确提交。原库/商城源/旧 12 Run/Provider/230 L0 不触。
- 首次 apply 在首条 Composition 事务前因新库缺 `meta_org/meta_workspace` 失败。只读对账确认 Composition/Lock/Installation/Command/Decision 全为 0，原安装 state/intent 保留。先通过 `orgs.ensure_org`、`workspaces_catalog.ensure_workspace` 的正式目录 Owner 在新库补正并独立 SQL 回读，修复 bootstrap 入口；随后用**新** state 及同一 exact 输入/幂等前缀重试，旧失败 state 不覆盖。
