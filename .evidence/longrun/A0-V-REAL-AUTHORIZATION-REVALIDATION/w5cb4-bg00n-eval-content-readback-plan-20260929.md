# W5CB4 BG-00n｜Eval 来源对象内容读回与哈希权威方案入口

## 上位方案及当前事实

231 首链与 AIP-4 E1A/E1B 要求真实可复验来源与脱敏证明，Registry 不保存业务行。BG-00m 已要求 `aip_artifact.content_ref` 与 Receipt→source exact lineage，但没有读回任何对象字节。当前签名增长包 `content/evals/placeholder.json` 仍 `BLOCKED`；同包 `w03-l05-dry-run-cases.json` 明文自称 dryRun，属于 D3 W03/L05 Logic/Widget 测试矩阵，不可充当 D01 Skill Eval。当前 9000 无监听，仓库 `object_store.py` 有 S3 `get_bytes`、`tenant_prefix.py` 有 workspace 前缀守卫，尚未见 G2 Eval 对象格式/签发 Owner 合同。

## 本波先做的权威闭合

1. 复习 228 G2 产品边界与 AIP-4 E1A 的 Dataset/Case/Receipt 定义，先冻结对象地址形式、source 内容格式、Receipt 签发字段及其 Owner；不得凭通用 `aip_artifact` 行或旧 dry-run 样例自行声称生产来源。
2. 在不写当前库、不读商城源的前提下核对象存储可用性及 tenant-safe 读取路径；若无法提供真实隔离对象存储，先对纯解析/hash/字段合同做 RED 与可复验实现，存储集成保持未验，不把注入的测试字节当业务验收。
3. 可行性收敛：当前没有 G2 Eval 正式内容格式，也没有可用的 9000 对象存储；在此状态下不能把任意 JSON 样例定义成正式 Dataset/Receipt，也不能让现有隔离样例成为对象存储正例。本波精确新增 `services/aos-api/aos_api/aip_eval_object_reader.py` 和 `services/aos-api/tests/aip/test_aip_eval_object_reader.py`：为将来的同事务 producer 提供可调用的对象字节读回门，要求 `org/project/evals/` 精确 key、禁止路径转义、限制读取大小、回读字节 SHA-256 等于 exact digest；默认调用既有 `object_store.get_bytes`，测试只注入隔离字节源。现有 `get_bytes` 整体读入响应，故同时对 `services/aos-api/aos_api/object_store.py` 与 `services/aos-api/tests/test_object_store.py` 做向后兼容的可选响应上限，读取时最多取上限+1 字节；HTTP 错误正文最多读取 200 字节。不能把读完再检查当作有界。RED 覆盖跨租户、越目录、缺对象、过大、hash 漂移；生产 DB 与 Registry 入口保持原 BG-00m 禁入条件，不暗设测试绕过。
4. 后续波再与正式 G2 producer/issuer 接线，在已确定的内容格式下校验字段 allowlist、case count、Receipt 签发与撤销，并在隔离对象存储完成真实读回；只注入测试字节的单元 GREEN 不能声称存储集成或 D01 通过。

本波 reader 的单元 GREEN 只证明字节门可复用，未与 Dataset 登记、正式存储或 G2 签发接线。当前 D01、Skill 发布/Binding、Host/worker/Provider 与自然首链仍禁入；不触碰 230 L0、旧 12 Run 或当前业务库。
