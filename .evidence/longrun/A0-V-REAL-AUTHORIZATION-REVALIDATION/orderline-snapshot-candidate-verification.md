# SC4-5e5 订单明细观察快照候选

2026-09-14，基线f25659a9，Lease A0-V-SC4-ORDERLINE-SNAPSHOT-CANDIDATE，m1不push。

新增prepare_niushop_orderline_candidate.py与1.9.0；原1.8.0树d0f2a557e0749a4bc753e18954a2dce368f632d7be8bd3247cece69d04e0c575不变。仅bundle/p06/evals相对变化；不含发布安装或镜像资格。

复用现有v3纯映射，不改运行机制。退款[-3,0,3]通过显式状态映射严格执行，原业务值保留；零create_time/refund_action_time保持未知，无createdAt补值；价格/货品金额规范映射，不声称净收入或实付金额。Order/Product/SKU关联未物化，父订单创建时间/删除语义必须后续真实处理。

37 passed/7既有警告/6.61s，包括原订单/v3回归；六类合成规范对象评估通过，完整AR2检查1909/187/93且五错误数组空，diff-check通过。未重新扫描客户明细、未写源库/主库，未生成Fulfillment。

SC4-5e5：订单明细1.9.0静态候选完成，37项针对性回归通过，六类静态评估通过；create_time=0保持未知，经营窗口与三类关系待真实Owner。新树b52f6a76334528d7c8cde06e802252e6934dd4ead29c35219f976d3f55413e01；静态6/12、主库仍先前核实2/12。下一物流隐私遮罩契约及剩余映射，再关联/实际补齐/完整首链。
