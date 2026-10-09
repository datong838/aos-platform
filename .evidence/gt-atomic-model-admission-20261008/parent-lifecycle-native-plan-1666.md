# 父生命周期接入前原生负门

基线96b02d10b/AOS-001666，原atomic ACTIVE Lease至19:36:28UTC，无新writer。上一波已确认schema差异；本波用新完整原signedRule、独立批准Target/Judge、两case同nativecaller验证，而不是任意伪造父记录。

精确修改 services/aos-api/tests/aip/test_physical_capacity_occupation_pg.py，新增原生回归：两新父hold/hash/xmin/full4leg、三桶风险10、真实null价格、普通 _reservation_by_id 不能认新purpose父、runtime不能转换原父到cost_pending、负门后所有parent/buckets原样；原wholevalidator仍复核成功，caller最后rollback，独立回读原两父0、xidABORTED。不创建假settlement/Usage，不赋价格，不删历史资源。

新增本Task目录 parent-lifecycle-native-r1 内runner/attempt/result/proof及本方案/复审。Judge既有fixture仍输出其独立新child，exact三helper copy及旧原件hash保护；原nativefixture创建新隔离库，保留不删。此次不声称实现了可信settlement；若无完整输入源，不为满足“实现”引入unusedhelper或放宽旧held。确认实际负门后继续全父私有协议接入。
