# 候选引用层级修订验证

基线 m1 745b6741，权威 AOS-001348，Source Task/Lease ACTIVE。本文件仅记录候选 producer 中的引用类型修订，不是完整 Source 交付。

督导发现 BasisCandidate 使用正式账户类型，但 Store 实际读 account candidate。先补方案，再新增三项反例：原正式账户类型在 basis/source 输入、原正式 basis 类型在 source 输入均须拒绝。修改前实际 3 failed、30 deselected、6.26 秒（candidate-ref-red.log）。

最小修订使用 ProviderPhysicalAccountCandidateRevision 与 ProviderCapacityBasisCandidateRevision，更新契约和两个测试文件，不修改 Store、SQL 或原通用 Action。修订后四文件专项/相邻实际 98 passed、8 warnings、76.46 秒（candidate-ref-adjacent.log）；包含候选契约与实际隔离 PG producer、原申请和独立审批。警告包括故意构造非法类型的序列化提示，不当作业务通过证据。compileall 与 git diff --check 通过。

只读督导复审确认方案/契约/实际候选 ID 一致，未发现新问题；复审发生时测试未终结，本记录依据随后终结日志补充 GREEN。此为受邀审查，不证明后台自主值班。

候选表固定未验证、不可执行，不存在正式账户映射、容量签发或占额入口。正式 Source 专用独立审批、账户归一、供应商来源适用性和时效、epoch 提交协调、受限 issuer、正式消费器拒绝候选类型仍待实现。完整 Source Task 与 b90 Task 保持 ACTIVE，当前真库与现实 Provider 未触碰；无页面改动，浏览器验收不适用。没有声明自然业务首链完成。
