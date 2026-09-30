# W5CB4 BG00dg｜BI 签名职责模板严格 schema 文件级方案

## 上位与定位

231-1 N4/N8 要精确职责计划，231-2 要包内容按字节签名与安装 lock 绑定，231-5 的人工批准/评审是独立运行门。BG00df 先封 production profile 冒充职责模板；当前签名包无 BI 模板。本波只提供将来新候选版本可携带的**纯内容 schema 和解析门**，不创建/发布新版本、不改当前 signed tree、Registry/DB、Host/worker，也不填六个真实 assignee。

## 文件级设计

1. 新增 `aip_business_investigation_responsibility_template.py`：固定 schema ID、template ID、profile、read-only safety mode、修订号和六个 slot 的 ID/责任类型/能力/return stage；严格禁止多/少/重复/漂移。六 slot canonical blueprint 搬到同模块的不可变常量，供现有 `ecommerce_business_investigation_aip_authority.py` 导入，避免两份来源分叉。模板不含 assignee、批准或预算值。
2. `aip_responsibility_template_authority.py`：对已核 active 安装/签名/lock/hash 字节，按精确 schema ID 解析既有 media 或新 BI 模板；未知 schema、production profile 或错类型拒绝。仅当 ref 为 `ResponsibilityTemplateRevision` 且安装行和字节均匹配可通过。本地 BI 兼容分支暂保留，以免在新版本发布前破坏历史路径；不能计作当前签名正向。
3. `tests/aip/test_aip_responsibility_template_authority.py`、`tests/test_ecommerce_business_investigation_aip_authority.py` 先 RED：独立临时 release mirror 中精确 BI JSON/Registry 行正向，六 slot 任一漂移、未知 schema、错 digest/版本/tenant 负向；materializer 构建 slot 与模板 canonical 常量一致。再最小实现与相邻累计。

## 收口门

专项、相邻回归、`py_compile`、`git diff --check`、方案一致性复审；验收只说隔离合同代码 GREEN，不说当前签名 release 已更新或首链可运行。下一波独立处理新候选版本与 manifest/签名/安装迁移。
