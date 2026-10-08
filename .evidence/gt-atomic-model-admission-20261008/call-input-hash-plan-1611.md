# 原输入哈希兼容专项

原Input producer验证encode(sha256(raw),hex)，原Suite/Intent inputHash为raw64；新prepared_call_occupation.input_hash要求sha256前缀不相容。先新全bootstrap原Source/4leg风险准备，在实际原case输入hash上取pg_constraint.conbin并由数据库执行原CHECK，预期TRUE而现FALSE形成RED。修复只删新input_hash正则的前缀，不改content_hash的既有sha256前缀，不改原Input/Intent/预算/Source/COMMIT拒绝门。另新独立库GREEN核raw接受、带前缀/长度错/大小写错拒绝、runtimeDML拒绝、原完整Source回归；独立回滚/Source/身份/既有资源保存。父Task完整准入与自然首链仍未完成。

候选①精确原Input-Intent调用准备producer（atomic授权，依本兼容门及当前plan/Source）；②原Target实际结果→Judge输入（Judge授权，依已知提交可信结果）。本轮先修候选①的已复现前置缺口。
