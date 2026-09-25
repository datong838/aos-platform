# W5c8j｜保存源组哈希同事务校验可行性审计

## 判定

`jsonb::text` **不能**作为历史 `_digest` 的输入。专用 PG 对三个 binding/manifest 形态（含嵌套、Unicode、空格、负小数）逐一计算，三项均与 Python `json.dumps(ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)` 的 SHA-256 不同。最小例：Python `{"a":1,"b":2}`，PG `jsonb::text` 为 `{"a": 1, "b": 2}`。不能简单删除空格，因为字符串值允许空格；键序、数值/Unicode 转义等还有独立语义风险。

在同样三项中，若把 Python 精确 canonical UTF-8 文本作为参数，PG `sha256(convert_to(text,'UTF8'))` 与 `_digest` 相等，且 `text::jsonb` 等于原 JSONB。这只是**字节见证方案的可行性样本**，不等于历史表已保存该文本或数据库已可靠证明文本来自原始写入。

## 原始合同与缺口

- `pipeline_snapshot_group_claim_owner.py` 写入 `binding JSONB` 与 Python `_digest(body)`，`pipeline_snapshot_group_input_owner.py`/原 ingress 写入 `manifest JSONB` 与 Python 摘要；`a0v_045` 的 RLS、不可变触发器、延迟完整性触发器不重新计算 canonical hash。
- `PipelineSnapshotGroupLocator` 读时由 Python 复算 binding/manifest 哈希及成员序、actor、cutoff；这是只读证据，不能先读后跨连接调用旧 ACK。
- `a0v_094` Host guard 是单事务入口，但不能替代源组 hash 检验。W5c8i 撤旧 EXECUTE 仅在隔离迁移 head 生效；真实数据库仍未迁移。

## 安全替代候选（W5c8k 先设计，不在本波执行）

1. 新写入：为 claim/input 追加不可变的精确 canonical UTF-8 文本见证字段，原写入事务同时保存该文本、JSONB 与摘要。DB 侧至少核文本能解析为同一 JSONB、文本 SHA-256 等于原 hash、文本大小与结构上界；不能接受 caller 自报“已验证”的布尔值。
2. 历史数据：只在隔离副本做逐行 Python 原算法回算，比对已存摘要及 JSONB；不一致记录冻结，不自动修正。明确可回填数量、版本与审批边界后再设计真实库迁移；不能给未见证的原组默认通过。
3. 新对账 SQL：在同一个 runtime 写事务按 Host→Delivery 锁序调用 `a0v_094`，然后重核原 PREPARING/Occurrence/Origin、唯一保存组及全部成员、精确文本见证与双 Receipt，最后原 attempt/token 的 unknown→acked；过期 claimed 独立门。任何前置缺失都零写入，未知提交只读对账。
4. 不采用的捷径：`jsonb::text` 摘要、空格剔除、仅比较表中现成 hash、Python 预读后调用另开连接 Store、把 W5c8g 证据当写授权、恢复旧函数 EXECUTE。

本文件为设计审计，不授权真实迁移、Worker 接线、源调用或旧 attempt 重发。下一波需先测试历史 canonical 见证能否从现存 JSONB **无歧义重建且与原 hash 匹配**；仅三样本相等不足以宣称全量可回填。
