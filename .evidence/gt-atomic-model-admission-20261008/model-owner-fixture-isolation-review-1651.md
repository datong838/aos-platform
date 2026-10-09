# 新鲜原申请证据隔离修复检查点

Rules：231、原 atomic Task/Lease、原 Model 隔离合同与技术方案；新增逻辑仅测试 fixture 的证据目录选择，不改业务 Owner/预算/旧 Skill/迁移。

原技术方案要求后继输入接线使用新鲜原申请，不复用过期审批。原测试固定两个 helper/result 路径会覆写历史证据；现增加显式且闭合的独立 evidence 子目录入口，原默认路径不变。新路径必须在原 Main evidence 内、不得就是原根；必须含字节完全相同的原 helper，whole 模式还要求原 certificate fixture；旧输出已存在即拒绝，不加载被篡改 helper、不删除旧文件。

RED：3 failed，缺新隔离入口。GREEN：5 passed，覆盖外部路径、原根误用、默认兼容、合法 byte-exact helper、已知旧输出保护与恶意 helper 不加载；whole 原 helper 完整性同测。

第一原生尝试在旧 Colima 5434 的 setup 迁移阶段 DiskFull，主体未运行；保留 aos_test_910262635381_ti4_test、attempt/result/log。未删除旧卷库，也未更换正式库。切换经过精确 ID/volume/capacity 门的外置盘 Desktop 原隔离容器 5441，用独立新数据库/新证据目录：r2 原 single Owner 1 passed/7 warnings/8.83s；r3 原 whole-plan rollback 1 passed/7 warnings/9.76s。

独立原生 SERIALIZABLE READ ONLY 核对两个新库、三个原申请 canonical hash、Model/Quota typed hash、实际 xid 状态与原表：r2 的原 legacy hold fixture xid committed、hold=1；r3 的 joint 准备 caller xid aborted、两个 hold=0。首次验证器错误假设两者均 aborted，已保留该只读验证失败记录并按原测试明文合同纠正；没有重发任何写操作。AgentRun/ModelCapacity/case-result 全部为零，原两份历史 legal fixture JSON hash 未变，原 Source C verifier SHA 未变且容器未重启。

这修复的是连续施工的可验证证据隔离，完整 Model/input/实际请求 token/context/输出硬限制接线仍未完成。原全 Task 未 Delivery；不宣称实际 Model 质量、正式首链或 Source 实际完成时限通过。上一 Prime 独立审阅 daemon 归属失败仍仅局部待恢复；本轮本地代码/方案自审与真实原生验证，不伪称独立模型 PASS。

下一波：沿 model-input-envelope-next-plan 与本次新鲜原 Suite/case/Model 原表，复核真实输入 producer 及 Artifact schema 到 wire JSON 的一致性，登记 Model 专用 transport 精确范围后实现完整请求绑定。新鲜批准记录用于调查，不等于正式执行权；后继实际写仍使用新的原审批/身份，不重放本次测试。主 Goal 保持 active。
