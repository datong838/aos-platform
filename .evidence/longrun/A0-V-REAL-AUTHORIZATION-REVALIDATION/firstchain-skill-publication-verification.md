# 首链D01/D02隔离契约发布验证

2026-09-11，北京时间13:03，基线2b61f033。任务A0V-FIRSTCHAIN-SKILL-PUBLICATION-20260911，仅指定自有克隆aos_upgrade_check_f1dc452abade。

新执行器先核验current_database；拒绝aos_meta_head/postgres/其他克隆/空身份及缺显式连接，后续所有Owner和Skill RouteAuthority依赖同一连接factory。旧R06 _skill_eval新增可选connect_factory/actor，原默认路径保持；不原样运行旧schema/head引导apply。首次克隆执行暴露RuntimePolicy DTO属性误用runtime_policy_id，写入前失败，改为policy_id后成功。

正式路径：Graph Owner→6case隔离Logic Eval→持久dry-run→Logic Publication→6case Skill Eval→Release Gate/Publication→Published Skill新revision。原r1不覆盖。

- D01 r2 hash150cbb469596c345aec64bab35bc6e81142c5e616c9fca72bd00d78fde889974。
- D02 r2 hash3526fb5194a3fbfa31eb848ff3556c0b3265b33468b7f8a5416370a5abcb70d0。

5项目标拒绝测试、3项旧技能引导契约测试及22项数据参谋逻辑测试合计30通过。克隆完整发布后再执行两次，518表逐表行数保持、exact结果一致。回读实际恢复库D01/D02 published计数仍0。本波Provider调用0、Binding激活0、经营计划产出0，返回CONTRACT_PREPARATION_ONLY。

边界：旧隔离adapter及Graph末尾契约标签属于契约验证，不是Provider质量或真实经营内容；没有把克隆权威复制到实际租户。执行器只面向受信本地连接，不提供公网入口；每个Logic开始前重新核验克隆，仍由调用者保持连接factory身份。报告ID/图/幂等键固定；未完成dry-run不会绕过Store的恢复约束。默认API仍1100b936，自动运行/扩展保持关闭。

下一波D03专属契约及首链绑定；同时沿实际分析执行路径核对可读画像/诊断/增长计划和来源生成，不能将上述契约标签视作完成。随后实际技能发布、职责、schema011候选安装兼容与激活、真实数据接入、首次分析与自然事件、内容续跑、八场景及观察。以上全部未完成。m1串行、不push、230 L0挂起。
