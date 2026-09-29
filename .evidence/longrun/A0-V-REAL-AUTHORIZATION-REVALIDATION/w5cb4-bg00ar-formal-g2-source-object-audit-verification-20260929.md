# W5CB4 BG-00ar｜正式 G2 来源与对象字节链只读审计

方案：`w5cb4-bg00ar-formal-g2-source-object-audit-plan-20260929.md`。本波没有业务写入、代码运行入口调整或对象 GET。

## 上位方案与当前制品

- `231-工作台业务闭环长程开发路径与波次实施计划.md` 要求真实授权来源、用途/脱敏及当前经营闭环证据；`228-电商增长参谋长G2三个核心数字同事与CustomerLite实施方案.md` 的 G2.2 要事实/渠道/Evals 与 Draft-only 负向门；AIP-4 `05-228-AIP-Evals发布门控决策谱系与可观测实施方案.md` 定三层资产/运行/发布门与真实数据来源/脱敏，但上述文件没有冻结 G2 Eval 具体 `sourceKind`、字段 allowlist、case count、对象 schema 或 redaction issuer/撤销责任。
- 当前签名包 `solution.ecommerce.growth/1.11.0/content/evals/placeholder.json` SHA256 `e90c23c9234793da6f76f82cc78ceddd677ce47c4c6ed7ced8397bb11d0a69c2`，内容是 `status=BLOCKED`、`Waiting for G2 review`，不是 Eval Dataset/Producer。R25 G2 组合方案自身标 `CODE_CONTROL_GREEN / OPERATIONAL_BLOCKED_LATER`，没有正式来源字节。

## 代码/现场精确边界

- `aip_eval_object_reader.read_verified_eval_object` 已要求 `org/project/evals/` key、2 MiB 有界 GET 与 SHA256；`rg -n read_verified_eval_object services/aos-api/aos_api services/aos-api/tests` 只命中定义和测试，Store/Writer/Runner 未调用。`aip_eval_authority_store._assert_artifact_snapshot_source` 与 BG-00aq writer 只核两条 Artifact metadata 的 tenant/hash/content_ref/sourceArtifactRef；不读取 bytes、不解析 payload/allowlist/cases、不核脱敏签名或撤销。其他 `sourceKind` 不经过该门。
- 当前 `aos_current_preview_20260927@a0v_114` READ ONLY：org-org/dev-project Dataset/Suite/ExecutionReceipt 各0，Eval snapshot/redaction Artifact `[]`，正式 Eval writer role0。固定 MinIO image inspect 退出1，19000 LISTEN 查退出1；真实 S3 往返仍未执行。

判定：BG-00aq 只关闭 `artifact_snapshot` 的当前 metadata 漂移，正式 G2 source、脱敏 authority 和字节内容三段仍未建立。下一波 BG-00as 应在当前库只读前提下，优先审 `artifact_snapshot` content_ref→S3 key 与读取时机/回滚边界，形成不依赖未批准 sourceKind 的失败关闭最小实现方案；若无法做真实存储正向，不宣称业务 GREEN，转做 E03/BG-00 配置首链独立项。Host/worker/Provider/首链继续禁入。
