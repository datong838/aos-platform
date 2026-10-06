# 完整157原命令与事实组合检查点

基线377a7990/AOS-001439。仅追加三私有invoker函数，原29300byte模块前缀不变；没有安装157或新增公共Source授权。

read_source_command复用原canonical原文、identifier、exactrefs和signed time，packet五键，command原模型继承schemaVersion=1后六键，authentication四键；拒NULL/重复/缺失/额外键/非canonical/invalid UTF8，正向双tenant、原Source proposal/event版本2/1、四引用类型及identifier，按原protocol/maker/command canonical重算requestHash，authentication主体匹配及当前expiry。HTTPS issuer复核实际venv3.11 urlsplit行为，允许Unicode域名、IPv6/带scope/IPvFuture/空port/前导零有效port，拒userinfo、query/fragment、非法端口/hostname及NFKC新分隔符。27实际样本与原claims模型对照，不宣称全Unicode/所有IPv6输入穷尽证明。

read_source_command_facts在同实际SCRAM issuer session、SERIALIZABLE、publicationOwner、UTC、正向tenant原事务中调用全部上一段原事实/neutral及withdrawal检查，不取Python PASS。shared及真实distinct Evidence/反序Provider布局的原Source和xid/PID精确一致。36单字段/字节故障包括hash正确重算后的原Source/event hash或maker替换，仍被原事实拒绝；保存点后原文正向恢复。普通runtime和issuer逐一不能直入三private helpers；临时harness/函数精确清理后原checker复验。

RED缺常量1FAIL7.06s，green-r1三真实正向FAIL（遗漏原继承schemaVersion；不是业务拒绝），修正六键后3PASS18.32s；全部专项42PASS151.09s。三文件最终168PASS154deselected7既有warnings/noSKIP483.70s/exit0，原transport真身份/签名破坏、Source、Evidence与原撤回竞争包含在累计中。AST/代码和方案whitespace检查通过；pytest原失败日志尾空格保留原字节/hash。所有日志和下一后缀依赖调查保留。

auth字段仍是untrusted hints，不验证JWT、不批准自由issuer/audience。policy/attestation/permit的refs仅typed，必须后缀从原登记材料独立验签/时点/部署/根/epoch；当前函数不写Source/global mapping或attempt。不证明公共S01安装审计、原生完整内部锁顺序、完整S17-S20后缀、Source实际COMMIT/consumer/finalTTL/自然首链。父Tasks ACTIVE，无SourceDelivery；下一直接装配同完整157的registry/signature后缀、稳定身份锁与pending原文，不改变最终退出合同。

正式DB/服务/Host/worker/Provider/商城源/旧Run/manual/外部效果/其他分支/push未操作；测试只自有保留隔离PG，库卷备份未删除，浏览器N/A（未安装SQL且无UI入口）。
