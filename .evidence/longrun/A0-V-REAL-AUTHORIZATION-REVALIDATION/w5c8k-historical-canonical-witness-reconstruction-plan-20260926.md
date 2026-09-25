# W5c8k｜历史源组 canonical 字节见证重建计划

## 上位与边界

承接 W5c8j `m1@81c4b870`/AOS-000672：PG `jsonb::text` 不是 Python `_digest` 的原始字节；精确 canonical 文本候选只在三个样本中被证明可由 PG 重算，不是历史回填授权。真实 a0v_096 尚未迁移、真实 Host profile 停止、原 12 Run 当前状态未知；本波不接 ACK/Worker、不开真实库、不读商城源，不重发未知 attempt。

## 文件级清单与判定

- 先复习 `ec_ingress_journal._digest`、`a0v_045`、`pipeline_snapshot_group_claim_owner.py`、`pipeline_snapshot_group_input_owner.py`、`pipeline_snapshot_group_locator.py`，核对原写入对象形态、JSONB 反序列化和存储 hash 是否可重建。
- 新增纯函数模块候选 `services/aos-api/aos_api/pipeline_snapshot_group_canonical_witness.py`：输入仅为从历史 JSONB 读回的 binding/manifest 与已存两个 hash，输出有大小界、可重新序列化的 exact UTF-8 文本见证及匹配结果；任何非法类型、NaN、hash 漂移都拒绝。不查询商城源，不写 DB，不提供授权布尔给 Worker。
- 新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c8k_historical_canonical_witness_pg.py`：先 RED，再在 `aos-a0v-test-only` 的 `aos_test_*` 库以真正 JSONB roundtrip 验正例；错误 hash、Unicode/空格、float/Decimal/非有限数、过大文本与跨对象置换拒绝，测试不读真实行。若现有 `chain_case` 可在有界时间取得原保存组，追加只读原组对照；否则不伪称历史全链已过。
- 仅在证明从现存 JSONB 重建文本与存储 hash 一致的**限定数据域**后，给 W5c8l 设计新不可变见证列/逐行受控回填。若类型/数字语义不可证明，冻结不实现；真实数据必须另立只读扫描计划与逐行拒绝报告，不能凭 fixture 直接回填。

## 九步

1. 上位产品/技术恢复约束、W5c8h/i/j、当前 authority/Git 与测试 profile 复核。
2. 本文件先提交，固定上述文件级范围和零真实 effect。
3. RED：JSONB roundtrip/错 hash/非法数/跨对象/大小界。
4. 仅做纯计算最小实现，不创建 SQL ACK/迁移或 Worker 入口。
5. 专项与相关累计、测试库 0、静态检查。
6. 浏览器只读验收；若被客户端阻断或租户目录不可用，记录不可验收。
7. 方案/代码一致性复审，特别历史文本并非原写入字节的证明范围、实网未扫描。
8. verification 提交，D-waves/AOS CAS/Prime 回读。
9. 自动下一波 W5c8l：先设计受控不可变见证列与历史逐行拒绝式回填；若本波 RED，则先修正确定的 JSONB 语义缺口。

230 L0 挂起，dev-org 仅零 canary；真实 closure 无授权，m1 唯一写者不 push、不动其他分支。
