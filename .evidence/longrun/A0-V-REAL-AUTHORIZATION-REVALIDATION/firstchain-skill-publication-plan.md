# 首链技能发布准备：先隔离契约，再真实业务产物

基线2b61f033。经营参谋当前D01/D02/D03均只有evaluated r1；D01/D02依赖material.collect，D03依赖strategy.plan。六职责另外需要content.review。新文本Route仅chat.answer，不能由此宣称其他任务/视频/音频可运行。

旧R06引导脚本schema为aip13_001、模型名model-qyh-text-dev、默认数据库连接，不能原样在当前恢复库执行。其隔离adapter输出明确“not Provider quality evidence”，Graph末尾返回输出契约标签。这些是历史契约测试，不是可读经营计划；本波不得把其结果充当真实业务验收。

最小分段：先在自有完整升级克隆aos_upgrade_check_f1dc452abade上，使用当前已发布模型/Route exact，正式物化D01/D02 Graph、契约Eval、Logic Publication、Skill Eval/Release/Published Skill。同请求恢复时先查既有权威，保持报告ID和幂等键稳定。D03不同专属实现下一段独立处理，不复制D01替代。Provider调用0，不激活Binding/Agent/安装，不写aos_meta_head。

实现文件scripts/a0v_firstchain_skill_publication.py；复用scripts/aip/bootstrap_r06_data_advisor_skill_authority.py既有纯契约生成方法，给_skill_eval增加显式connect_factory依赖注入，默认旧调用保持不变；新执行器所有Store使用同一显式克隆连接，Skill发布的RouteAuthority也显式注入。禁止默认回落到环境数据库。实测克隆发布+重放逐表计数、scope和模型引用保持；拒绝非允许克隆目标的测试必须先于写入。

后续真实模型产物验收另立门：使用真实已就绪店铺来源、验证可读画像/诊断/增长计划内容和引用，exact评审和内容承接继续原授权链。若当前Graph仅契约标签，不能通过这些结果宣布其经营功能完成；沿真实执行路径定位并实现产物生成后再验收。

## 2026-09-12 正式首链契约物化

已核实生产路径分别是 PortraitGenerationService、DiagnosisGenerationService、GrowthPlanGenerationService，经保留正文的 AipAgentRunExecutor 和可信 Receiver 落可读产物；历史 Graph 尾部标签只用于隔离契约，不是这些 Service 的产物。保持上述生产服务不变，先补其需要的正式 D01/D02/D03 Published Skill 权威，再做自然调度与真实产物验收。

模型/Route r2 已正式发布且治理有效。新脚本 scripts/a0v_firstchain_contract_materialize.py 提供明确 --apply 的唯一两个目标（aos_text_renewal_20260912 克隆、aos_meta_head 当前开发库），所有 Store 继续显式同一连接。复用 scripts/a0v_firstchain_skill_publication.py 的共同实现，旧 prepare_contracts 的 clone-only 守卫保持；新入口每项开始前验证 exact DB。先克隆三项+重放，后主库三项+重放。调用生产 Owner/Eval/Release/Skill Publication，不复制克隆 Gate。仅物化契约，ProviderCalls=0、Binding/Agent激活=0、业务计划=0。

具体改动 scripts/a0v_firstchain_skill_publication.py（提取共同流程）、scripts/a0v_formal_text_model_renewal.py（提取已验证连接供复用）、新增入口及 services/aos-api/tests/extension_runtime/ 目标拒绝测试。保留旧 evaluated r1、固定图及已有已发布版本，不覆盖数据。后续步骤依次是 Capability/Skill Binding、职责计划、源配置与 enabled、真实画像/诊断/方案和 exact 评审承接。

真实发布后进度审计误报：latest skill 从 evaluated 到 published 后 evaluatedSkillCount 由 37 降至 34，检查器把正常晋级当成定义缺失。scripts/a0v_agent_runtime_readiness_dependency.py 的定义准备门改为 evaluated+published（查询已按每个技能最新版本去重）；publishedSkills 门仍要求真实 published。保留两种原始计数以便审计，不把发布代替 Binding/运行就绪。回归测试覆盖部分发布不退回 REPAIR_CANONICAL_SKILL_DEFINITIONS，真正缺失仍阻止。
