# 完整签名原生接线验收
Rules：231、单m1、Task精确隔离、原Source/审批/预算不替代、未知结果不重放。
候选1：已授权完整新版本准入的原生证书集合正向，依赖原C verifier/Issuer Root和新来源同caller；选择此步。候选2：正式Root/native部署，依赖正式独立签名来源，不以实验Root代替。
复用已登记原Source+两原批准申请的全新保留DB runner，不重放旧attempt。新安装只在owned DB、caller SERIAL snapshot之前：原VERIFY完整4条DDL（没有改写）、新delegate artifact和测试proxy。Root由测试持有、私钥仅内存。Source与Owner保持真实原函数；各case identity key预先绑定后才构建新origin，四条原签名domain逐一签名；同一caller验证成功后独立负门签名/缺腿/重复/另caller/noncanonical/canary以及正向回读。最后rollback、独立xid aborted与原父hold零残留。原七门不动、不写正式DB、不发Provider、不签发正式Root、不声明完整准入COMMIT或Task Delivery。
精确新增文件仅本folder与原JudgeTask对应freshchild；产品不改。
R4：修正测试窗口，使用新签发证书至原Judge request expiresAt与预发布Root validUntil的较小值；原150秒审批/Source/Root期限不改，旧r1-r3签名不复用，不延长任何原批准对象。记录新证书正向调用前/末回读前的真实DBclock，并新增真实签名但已过期负门。Base64猜测已被原表达式实际SQL推翻，不改产品kernel。

R7：R6原生四签名/七证书负门/rollback已完成，但后续原Source整体相邻及teardown因JWT当前性到期RED。删去本probe内1720已完成的5来源负门和重复origin构造，证书初始正向一次、全部7负门、末回读一次，delegate本身仍两次原生来源与全claim核验。完整原Source相邻函数保持原样执行，不放宽任何期限/身份规则。
