# D01/D02/D03 正式契约物化验收

2026-09-12T01:41:37Z，基线 9251a025。使用用户持续开发授权，原 clone-only prepare_contracts 入口保持原限制；新增固定当前开发库/克隆入口，复用共同 Owner/Eval/Release 流程，未执行模型或业务阶段。

实际生产路径已核实为 PortraitGenerationService、DiagnosisGenerationService、GrowthPlanGenerationService + retained-output Executor +可信 Receiver；Graph 标签是隔离契约的输出，不拿它替代经营正文验收，也不因此改坏已有生产服务。

克隆 D01/D02/D03 各 6 case 契约报告通过，正式发布 Skill r2。重放 524 表计数不变。主库写入前备份 aos_meta_head-before-firstchain-contract.dump：4,642,861 bytes，SHA256 3f57bcbec68ed67f0abb6496206fa2e1d70ca784c55d59ff99ba906b4e6fab41。

主库三项各自生成本库 Gate/Publication，并发布 r2，原 r1 不覆盖。完整 exact refs 见 firstchain-contract-main.json。再次执行 227 个 AIP 表计数零新增；223 个租户 AIP 表中 canary 的排序内容摘要与基线克隆一致。结果 ProviderCalls=0、BusinessPlansGenerated=0、BindingsActivated=0。

修复进度审计错误：published 晋级不再使 evaluatedSkills 定义准备门退回；34 evaluated+3 published=37 个已评测定义，真正少一项仍拒绝。保留 published 门及其他运行门。18 项目标守卫/旧克隆限制/进度审计测试通过，AR2-7 验证通过。Scope 检查为受信本地显式连接保护，不是面向公网的授权入口。

剩余依赖：3/37 个 Published Skill、3/37 个 Logic Publication，当前还没有 Frozen EvalContract、Capability/Skill Binding、激活数字同事或责任计划。下一波先从 exact 已发布报告和 Release 冻结三项 EvalContract，建立有来源的许可/数据依赖，再正式 Binding；模型健康在实际评估时重新检查。随后源配置/启用与自然首链、八场景、连续观察仍待完成。不 push，230 L0 挂起。
