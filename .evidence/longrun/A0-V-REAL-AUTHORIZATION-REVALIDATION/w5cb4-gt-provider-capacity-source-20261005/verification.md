# 正式容量 Source 施工中的候选阶段检查点

基线 m1 745b6741 / AOS-001348。当前仅完成严格 claim 契约与 account/basis 不可变候选生产；完整 Source Task 不交付、不关闭。

契约缺模块 RED 27 failed/6.05 秒；契约初步 GREEN 27 passed/6.30 秒；加入 native 变异反例后契约及原申请/审批相邻 86 passed/63.59 秒。原签名 Provider、原 EvidenceBundle、实际本地 HTTPS OIDC Owner 先形成 producer RED 1 failed/7.24 秒，再初步 31 passed/7.40 秒。候选 producer 相邻修订前 95 passed/74.63 秒。全部终结日志在本目录，测试-only 事实不作现实供应商证明。

督导指出候选读取使用正式引用类型。先补方案和三项反例，实际 3 failed/6.26 秒，再将候选账户/basis 引用改为专门 CandidateRevision。最终四文件实际 98 passed/76.46 秒，编译与精确 diff 检查通过。详细记录见 candidate-reference-verification.md。无页面更改，浏览器验收不适用。

Store 同原 SERIAL caller 核 positive tenant/OIDC/current Owner、exact Provider 当前 head、原 frozen 未撤回 Evidence 元数据、候选完整 DTO、原 SQL canonical hash 与 maker；basis 重验 account candidate 及其 Provider/证据。幂等冲突拒绝，same key/body/maker 返回原候选。实际测试含 Owner/provider/hash/revoke/native变异、不可更新/删除/截断及 canary 无记录。

a147 只有 candidate 表、FORCE RLS、append-only、根字段白名单/必填与 hash、固定 CANDIDATE_ONLY_NO_CAPACITY_NO_START、basisVerified=false/executionAllowed=false。runtime 直接写入仍是不可信候选：SQL 不负责完整 nested DTO 或签名来源核验。客户端账户 ID/fingerprint 不证明归属或全域唯一；当前候选元数据读取不证明 revoke 与提交 epoch 竞争闭合。上述必须由后继专用批准、受限 issuer 和正式消费器完整重验。

完整 Source 专用批准、真实供应商依据/适用性/时效、稳定账户双向归一、epoch 与受限身份原子签发及消费器仍 pending。原 allocation approval 不能替代新计量模式批准；速率窗口不能偷换 inflight token 上界。共享 occupation/旧占用正式切换/一次 Intent/实际 transport/Usage/Report/Gate、b90 八事实实际 COMMIT/API/ToolBinding 和自然业务首链未完成。

仅 disposable PG 5433 测试；未访问/迁移/重启当前142库，未开启 Host/worker/现实 Provider、读取 Secret/商城源或回放旧 Run。m1 单写/no push。督导受邀复审有实际发现；自主后台有效报告与连续值班仍因429未验收。
