# W5CB4 BG-00ap｜Dataset Artifact/脱敏 Receipt 当前来源只读审查

## 边界

BG-00ao 只证明同事务 persisted Dataset/Suite/case exact ref。它的 test-only manifest 是 `selection_snapshot`，不含真实对象字节和正式脱敏签发。按 BG-00k/n、AIP-4 Dataset source、231 真数据合同，本波只读核 AIP Artifact source/ref、redaction Receipt、对象存储和正式 G2 producer 的实际责任与现时可用性。先确定最小合法下一代码点；不把 metadata 行或测试对象当业务真源，不读商城源、不写当前库。

## 文件级核查

1. 读取 `aip_eval_authority_store.py` 的 Dataset 登记、`EvalDatasetManifest`、Artifact/redaction source check，BG-00k/n/o 方案和相关 S3 reader/Receipt 合同；查是否已有可复用的同事务只读当前 source 方法，避免复制安全逻辑。
2. 当前 `aos_current_preview_20260927@a0v114` 在 READ ONLY 事务核 Dataset/Suite、`aip_artifact` 对应 Eval snapshot/redaction 类型计数、G2 signed placeholder；S3/19000 当前服务与已批准来源。只做 counts/hash，不暴露原始商城数据或凭据。
3. 形成精确风险、下一波 RED/最小实现点或外部 authority blocker。若 S3/G2 未就绪，转可独立完成的代码合同；Host/worker/Provider 继续禁入。
