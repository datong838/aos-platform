# W5CB4 BG-00l｜当前 D01 Eval 来源生产者与签发权威只读裁剪

## 上位方案与目标

复习 231 首链、228 G2 三同事、AIP-4 E1A/E1B 与栖月汇只读数据合同。当前签名包的 `content/evals/placeholder.json` 明示 G2 Evals `BLOCKED`；D01 Skill evaluated 仅是历史目录状态，当前 canonical Eval 事实为空。BG-00k 已加 `artifact_snapshot` 同事务元数据登记门，但没有来源生产者。

本波只读定位最小合法 producer/签发接口及独立 Judge/Target executor 权威，形成可编码的下一波文件级清单。检查当前签名 Receipt 与包内容、生产代码中 `eval_dataset_snapshot`/`redaction_receipt` 的写入路径、既有 Artifact Store、AIP-4 Manifest 与 G2 责任边界。发现缺少正式身份或源时仅阻断该实例，明确可独立推进的合同/负向门，不向真实库写伪来源。

## 精确文件与验证

- 只新增本方案、同目录 verification；不改生产代码或测试。用 `rg` 和有界文件读取确认 producer/issuer/Case/Judge/Target 权威是否存在，并核当前签名包 `BLOCKED` 原文。对当前库仅复用本日 BG-00i 只读零行证据与 BG-00k API reload/健康读回，不再次运行 Eval/安装/Host。
- 若生产者或签发权威缺失，RED 是当前正式来源无法构造；下波方案应先冻结 Owner、内容存储与签发合同，隔离 PG 覆盖非法签发与内容哈希漂移，不能用测试样例填补正式包。

## 边界

不读取商城源，不写当前库，不启 Runtime Host/worker/Provider，不重放旧 Run、手工 run_definition 或触碰 230 L0。只读审计不算 G2、D01 Eval 或首链通过；不凭代码搜索缺失声称所有外部 Owner 均不存在。
