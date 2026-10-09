# 原生 Source 直接消费诊断验收

基线 292736bf / AOS-001623。原 Source Task 仍 ACTIVE、无 Delivery；现有未追踪产品实现保持原字节，不隐含整体交付。

原完整迁移独立库 aos_test_d9d1ab409a6b_ti4_test，真实签名 Source、SCRAM 同 caller、四腿 Plan、Intent、call、typed 正向成立。三类额外字段（root/source_ref/tenant）均被直接消费者接受，返回 Source 与原对象一致，未变命令再调用正向。真实 RED 为要求三项固定拒绝的断言失败：1 failed / 57.29 秒 / 7 已知 warnings；不是连接或鉴权故障。caller xid11765/pid23607，executionAllowed=false。断言先于后续完整 manifest/COMMIT 负门，本次不宣称那些后续验证完成。

根因：序列化 model_dump 后再次验证丢弃副本额外字段；保留原实例验证可让既有 revalidate_instances/extra forbid 覆盖嵌套命令。建议仅修改原消费者第143行实例验证；补丁为建议文件，尚未应用，未宣称 GREEN。

独立只读回读 caller xid aborted，六占用表全0，Source1，occupation NOLOGIN/member0，临时 probe0、producer移除，31旧资源按1619实际授权重启基线一致。原产品 SHA256 e6b46538babab94fb56a5aca005cee0aae6190d3e7958c57ba7c10b66846686d 未变化。没有实际执行、当前权威库写入、服务重启、Provider、其他分支或 Goal 修改。

仅本独立诊断合同收口。下一登记原 Source Task：先补方案，再一行产品修复及三个真实负门 GREEN；补 shared/isolated 两布局原 Source、角色 ACL、并发、签名撤销与旧 issuer-consumer 专项累计，逐项明确未追踪旧实现完整精确提交边界。实际准入/费用/Judge真实输入候选仍依赖真实结果和正式身份，不以本 RED/修复方案越过。
