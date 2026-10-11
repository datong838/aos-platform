# 栖月汇恢复继任签名入口

承接e529ab612/AOS-001840的实际build/qualification。新增独立sign_ecommerce_qyh_recovery_candidates.py，复用原Growth1.13 validate_qualification以及原current signer validate_build/sign实现；通过独立import模块仅设置core1.4.3版本表、build_ecommerce_qyh_recovery_candidates.py profile和独立local candidate keyId，不修改旧函数/文件或全局导入实例。

公开validate-only模式：输入build-dir/build-receipt/qualification-receipt/state-dir，只读验证原精确hash、版本、SDK/依赖/runtime资格、2048heartbeat/cleanup、七tamper、Git祖先及source等原门，输出VALIDATED_UNSIGNED_BUILD_NO_SIGN。不得调用_key/sign或建state/output。签名模式的输出不得位于repo、build、state内且不可已存在，避免回执改变已验证输入或污染新state；原state不得重用/覆盖。未来实际local签名也不等于正式Root授权或发布。

先真正RED（--confcutdir避免无关DB自动夹具），新增测试基于上轮真实build/receipt/qualification：只读正向、错coordinate/heartbeat/receipt绑定负向、旧profile保持、禁输入覆盖。相邻原1.12/1.13/current signer及新候选回归；方案/代码复审、实际只读CLI核验并独立输出/hash回读。本Task不运行签名、不生成key、不写正式DB/Registry/安装/HTTP。

下一安全候选：原正式signature来源/HTTP恢复入口门调查；正式切换、当前配置预算和浏览器仍未完成，不能用此包准备代替实际交付。
