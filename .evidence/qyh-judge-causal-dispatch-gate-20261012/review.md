# 复审
原SER/role/double-scope/intent锁/version/Run running/重复不重发规则保留，只在新Judge INSERT之前追加同case/intent/tenant Target result_observed及case input一致读取。五反例旧行为DID NOT RAISE是真RED；修复后6新native+72相邻=78PASS0skip、7原warning。拒绝无Judge行/无version更新，正向一次与replay不重发通过。
旧judge_before_target消费者反例改用新owned fixture直接SQL生成旧格式错序，不调用新claim绕开拒绝；wrong_input反例同case双派发都使用错误输入，使应用关联门通过但原完整签名输入仍不匹配，readonly整体保持UNKNOWN。没有修改消费器、签名/时效规则或真实数据。
这是应用入口因果门，不是数据库不可绕过门；独立writer直接SQL仍可写错误日志，1943消费者拒绝证据保留。result_observed不是已验证签名，也不授正式Judge调用；完整producer/受限终结/Owner预算/签发当前权限仍缺，不打开Host/Provider/worker。
无迁移/新权限/HTTP或UI变化，不影响原Target或普通Logic/媒体路径。代码未部署冻结97bAPI，八台/自然首链未完成；保护22用户改动，m1精确提交不push。
