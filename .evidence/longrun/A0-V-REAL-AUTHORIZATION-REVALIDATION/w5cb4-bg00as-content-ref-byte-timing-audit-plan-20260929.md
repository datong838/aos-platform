# W5CB4 BG-00as｜Eval Artifact content_ref 到对象字节门审查

## Rules/上位方案

按 231/AIP-4/G2.2、BG-00n/aq/ar 现有代码与测试只读核 `content_ref` 编码、对象 key、字节读取时机、事务回滚。先定位最小点；若正式 source/object schema 和存储不可用，记录精确阻断并转 E03/BG-00 独立首链配置项，不改既有 Store 语义或伪造真实对象验收。当前库只读，不读商城源、不启 Host/worker/Provider。

## 文件级核查

1. 读 `aip_eval_authority_store.py`、`aip_eval_object_reader.py`、`object_store.py`、`tenant_prefix.py`、`aip_eval_pack_registry.py` 与现有 Dataset/Skill Publication 测试，查 `content_ref` 是否已是规范 S3 key，谁持有真实对象 GET 权限。
2. 核当前 signed G2 placeholder、MinIO/19000、当前 Dataset/Artifact 只读计数；确定能否 RED 后加最小接线，同时仍证明现有正常行为不退化。
3. 输出可执行下一波入口，区分机制可写与正式业务 authority 未具备。
