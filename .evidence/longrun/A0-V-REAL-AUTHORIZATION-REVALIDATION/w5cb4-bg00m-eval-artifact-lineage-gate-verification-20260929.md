# W5CB4 BG-00m｜Eval Artifact 地址与脱敏来源链门验证

方案 `w5cb4-bg00m-eval-artifact-lineage-gate-plan-20260929.md`；基线 `m1@886c03fb`、权威 `AOS-000861`。仅改 `AipEvalAuthorityStore` 的 `artifact_snapshot` 同事务查询条件与五个隔离测试文件，不加迁移或真实库写入。

## RED／GREEN

- RED：`pytest -q test_aip_eval_authority_store.py test_aip_eval_pack_registry.py -k 'direct_dataset_store_cannot_register_unlinked_artifact_receipt or artifact_snapshot_source_metadata_preflight_is_scoped_and_exact' --tb=short`，退出 1，`2 failed, 11 deselected`。缺非空内容地址或 Receipt 精确来源链时，旧 Store/Registry 未阻止 Dataset。
- GREEN：同命令退出 0，`2 passed, 11 deselected`。缺 source/Receipt 地址、只有 source 地址、Receipt 指错 hash、直调 Store 的未链接 Receipt 均失败关闭且 Dataset 行 0；同租户精确元数据正例仅在隔离 PG 成立。
- 七文件相邻回归排除已知 RETURN Action 正向用例：退出 0，`52 passed, 2 deselected`。全量 `-x`：退出 1，`53 passed, 1 failed`；唯一失败仍为交接已有 `REPAIR_ACTION_CURRENT_AUTHORITY_UNWIRED`，与本波无关，继续安全禁入。
- `python -m compileall -q` 本波六个 Python 文件退出 0；`git diff --check` 退出 0。没有浏览器路径变化。

## 复审与剩余风险

Store 的同一 scoped 事务先比对 source/Receipt 的 tenant、ID、type、hash、revision，再要求两个非空 `content_ref`，并将 Receipt `source.sourceArtifactRef` 与 manifest source 精确相等，最后才插入 Dataset。Registry inspect 仍委托同一 Store 条件；其他 source kind 没被本波宣称为正式来源。测试用 `test-only://` 地址只证明负向门与调用路径，不是对象存储读回，也不是业务验收。

当前签名 G2 Eval 仍 `BLOCKED`；地址非空无法证明字节、哈希、字段白名单、脱敏算法/签发身份或撤销。下一波应基于受控对象存储及现时签名包/Owner 建立真实内容读回和签发验证，在独立隔离环境证实，再考虑当前 D01。Judge/Target executor、正式 Eval、首链继续未完成；当前真实库只读，Host/worker/Provider 关闭。
