# Dataset 前规范输出校验

基线 d7a8dfae，D1 FR-D1-2 失败不推进断点。执行器目前 Dataset 先写成功状态，OT 后验证。将 ec_ot_writer.py 暴露无 I/O 的 validate_ot_output，复用 _build_sync_scope/_normalize_rows；ec_live_executor.py 在 Dataset 前调用。OT 写入自身继续校验以保护其他调用者。无效输出不能进入任一 sink，异常仍沿既有 DLQ 路径传播。

测试新增 tests/test_ec_ingress_preflight.py，调用真实 executor，替换源/transform及外部sink，以无类型和缺必需字段记录证明两个sink均未调用。空输入保留原行为。运行 OTWriter 与新专项。此措施不解决数据库/网络中途失败的跨落地点原子性，亦不改变 Dataset 当前吞持久化异常行为；后者列入后续清单。无真实源调用。
