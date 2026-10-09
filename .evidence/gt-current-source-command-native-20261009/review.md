# 当前消费者直接命令实例验证修复

使用 Rules：用户 AGENTS.md、aos-engineering-delivery、231、原publication-schema及Source-publication完整Task/Lease。基线55ac836f/AOS-001630，唯一thread/owner，两个原Task均经支持CAS按原scope续租，未夺锁/删除Lease。

实际新隔离库真实Source prepare/sign/finalize/COMMIT、不同SCRAM xid/PID的真实当前独立Owner正向消费成立，原命令重放一致。root/source_ref/tenant额外键三副本均被原消费者接受，拒绝断言真实RED：1FAILED27.45秒，Source hash/signature/provenance与清理独立核验通过。没有业务执行或当前权威库效果。

原publication-schema方案修改在代码之前。source_consumer.py仅两行model_validate(command.model_dump(...))改为model_validate(command)，沿原extra-forbid/revalidate_instances=always保留输入额外字段并重验。SQL/currentness/身份/签名/期限/锁/历史/旧issuance消费者不变。新原生专项1PASS23.75秒，三个变异均固定CAPACITY_CURRENT_SOURCE_REQUIRED拒绝，未变命令正常重放。Source仅非执行返回。

原两个消费者shared/distinct完整相邻4PASS184.42秒；原Source-publication方案与Lease另行登记后，在原独立Owner真实正向后持久化三个额外键拒绝及原命令重放。新增回归后两布局完整原独立Owner矩阵2PASS111.16秒，含原身份/权限/漂移/reader-first与writer-first/等待过期/撤销恢复。所有真实轮次7项既有warnings/noSKIP，原RED保留。

独立核验：本诊断RED/GREEN各1库Source签名/provenance/清理已核对；完整回归6个新保留库均Source签名/hash/finalized/原事务committed及provenance一致，角色NOLOGIN、临时四接口不存在、occupation表若未安装则按ABSENT记录（不冒充六表0），原31资源身份启动卷端口均不变。产品精确两行diff，原测试已有occupation fixture 6增1删受保护；Git仅stage新增13行回归hunk，原fixture改动仍保留未提交。首次stage行数断言误写14而失败，完整index SHA核对已通过；纠正为实际13后再核对，无撤销或重放测试。

到期调查并列保留：AOS1630的P0002失败源于自拟具名SQL22023断言，复核原publication/current消费合同只要求当前授权/期限拒绝及Python固定错误，并无此SQL代码要求。本次不为该断言改变SQL或旧拒绝语义，不将先前RED伪改成全绿；它的原Source当前性完整核查仍在原Task下，不阻断已登记安全修复。

独立模型review入口为此前Prime daemon ownership局部失败，本轮没有虚构PASS/重发旧attempt。此为精确输入验证修复、原生专项与完整相邻、代码/方案自洽核查；不收口原publication-schema/Source/epoch/legacy完整Task，不解决最终COMMIT时间语义、不批准正式安装/身份/Host/worker/Provider，也不证明自然首链或长期Goal完成。下一沿原合同继续完整Source交付核查、distinct提交时间与正式依赖门。
