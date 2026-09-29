# W5CB4 BG-00n｜Eval 来源对象内容读回与哈希权威方案入口

## 上位方案及当前事实

231 首链与 AIP-4 E1A/E1B 要求真实可复验来源与脱敏证明，Registry 不保存业务行。BG-00m 已要求 `aip_artifact.content_ref` 与 Receipt→source exact lineage，但没有读回任何对象字节。当前签名增长包 `content/evals/placeholder.json` 仍 `BLOCKED`；同包 `w03-l05-dry-run-cases.json` 明文自称 dryRun，属于 D3 W03/L05 Logic/Widget 测试矩阵，不可充当 D01 Skill Eval。当前 9000 无监听，仓库 `object_store.py` 有 S3 `get_bytes`、`tenant_prefix.py` 有 workspace 前缀守卫，尚未见 G2 Eval 对象格式/签发 Owner 合同。

## 本波先做的权威闭合

1. 复习 228 G2 产品边界与 AIP-4 E1A 的 Dataset/Case/Receipt 定义，先冻结对象地址形式、source 内容格式、Receipt 签发字段及其 Owner；不得凭通用 `aip_artifact` 行或旧 dry-run 样例自行声称生产来源。
2. 在不写当前库、不读商城源的前提下核对象存储可用性及 tenant-safe 读取路径；若无法提供真实隔离对象存储，先对纯解析/hash/字段合同做 RED 与可复验实现，存储集成保持未验，不把注入的测试字节当业务验收。
3. 文件级实现计划应限定 `aip_eval_authority_store.py`、受控内容 reader/合同模块及专项测试；要证明来源与 Receipt 的字节 SHA-256、对象 key 租户前缀、缺对象/漂移/跨租户失败关闭，并规划字段 allowlist、case count 与签发权威的独立验证。旧隔离 Eval 样例需明确迁移到合法内容 fixture，否则不能放宽生产门以保旧测试。

本入口是继续调查与设计，不是代码 GREEN。当前 D01、Skill 发布/Binding、Host/worker/Provider 与自然首链仍禁入。下一步先完成具体内容格式和可用测试存储的可行性证明，再定 RED/最小实现；不触碰 230 L0、旧 12 Run 或当前业务库。
