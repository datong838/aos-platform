# 接入批次不静默丢行

基线 df789e2c。复核 D1 FR-D1-2：失败不能推进 checkpoint。当前 OTWriter 的对象/关联构造器对缺失类型返回 None，混合批次会跳行后提交剩余记录，纯无效批次则返回零计数。

修改 ec_ot_writer.py 的 _normalize_rows：构造结果为 None 时抛固定 ValueError，整批在调用 checkpoint/store 前拒绝；错误不包含源行内容。空输入维持零计数，合法批次语义不变。不修改底层一致性 Owner 或数据库。

测试 test_ec_d1_ot_writer.py：缺失 ot、空 ot、空 link_type，分别纯无效与混合合法记录；验证异常且 apply_batch/checkpoint 无调用。先红后绿，运行既有 OTWriter 专项。真实配置仍缺，本修复不声明已完成真实同步。后续继续数据输入与经营首链装配。
