# W5CB4 E17-s3e｜签名 Guard 来源到配置候选读者文件级方案

## 上位与范围

- 231 首链和 E17-w 的八类运行配置候选是只读配置引导，不授权 Host。E17-s3d 证明 Model Eval Gate 缺正式执行 Owner，故先选择独立的 DataClassification/Egress 两项。
- BG00GO 已在全迁移隔离 PG 建立原 draft、签名 maker/独立 checker、批准事件、低权 consumer 原子 active/head/Receipt；其 `test_signed_guard_pair_consumes_and_provider_reads_exact_sources` 已验证 Provider 依赖精确读取，但未验证八候选读者识别该正式结果。

## 文件级次序

1. 只在 `services/aos-api/tests/aip/test_guard_policy_activation_pg.py` 既有签名双 Guard 正向测试中读取消费前 `read_candidates`，原 consumer 依次激活 Egress/Data 后，再读候选。断言两个字段各增加一，其他六字段不受此消费改变；缺项仍由实际读数决定，不假定全库空白。
2. 保持原双签、消费 Receipt/幂等和 `require_provider_dependencies` 原断言；不得用直接插 active 或改 `runtime_configuration_candidates.py` 让假数据通过。
3. 专项/邻接回归、编译与 diff check；仅测试中若原读者和原消费结果不相容才对生产读者另起最小方案。当前真实库只读，Host/worker/Provider关闭。

## 验收限度

全迁移隔离库正向仅证明两个合法来源可进入候选计数，不证明当前正式身份/策略、安装配置绑定、余六项或自然首链。未知消费效果只读对账，不重发。

## 验证结果

- 在原 `test_signed_guard_pair_consumes_and_provider_reads_exact_sources` 的签名 maker、独立 checker、原批准事件、低权原子 consumer 与 Receipt 回读之后，同事务可见的原 `read_candidates` 显示 `egress_policies` 和 `data_policies` 相对消费前各 `+1`；其他六字段逐项不变。原 Store 的精确 Provider 依赖校验与幂等回读仍通过。未直接插 active、未连接当前权威库。
- 专项 `test_signed_guard_pair_consumes_and_provider_reads_exact_sources` 退出0：1 passed；相邻原签名批准、普通 Store 对文字批准拒、候选读者合计9 passed/退出0；`py_compile`、`git diff --check` 退出0。
- 修改仅在测试文件9行，无生产逻辑改变；这与方案的“两个合法来源进入候选计数，但计数不授权安装/运行”一致。当前实例仍需正式签名身份、余六类配置、精确配置绑定、安装 operation/assignment、Host Owner 与首链证据。下波 E17-s3f 从六项中再选不依赖正式 Model Eval 身份的合法来源；优先 Network 或 Budget 的现成独立批准消费与候选读者联测。
