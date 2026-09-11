# 经营参谋恢复后的显式技能选择

基线4d57ef29，复习231-5/231-6、经营调查exact组合与Binding Owner。用户继续全权本地开发、m1串行、不push、230 L0挂起。本波不虚构经营计划、不绕过真实数据就绪。

当前核查：Provider1/Route1，但健康过期；37个evaluated技能无published版本、技能/能力绑定0、6实例均provisioning，职责计划0。旧审计currentPassedEvalGateCount=2包含Model/Route Gate，不能解释为37个技能中已有2个通过。10项全部能力只是总清单，不应把视频/语音绑定到文本路由。

恢复断点：经营调查组合和刷新协调器调用selected_skill_refs()，固定D01r2/D02r2/D03r4及旧hash。合法重发新技能会变化hash，当前代码无法通过常规绑定配置恢复。现有SkillBinding Owner在创建时已校验Skill exact、published/发布租户及能力覆盖，并通过版本/CAS控制激活；SkillBinding持有不可变SkillRevision外键。因此复用已激活Binding作为显式选择，无需另建选择表或从最新版猜测。

1. 保留旧常量作为兼容测试/历史引用；生产组合和刷新不再以其版本/hash作为运行配置。三个规范技能ID保持不变。
2. 从当前tenant的active SkillBinding为每个技能选唯一绑定。缺失或同时激活两个版本均拒绝；读取其绑定的不可变SkillRevision的hash，再核对该tenant的published Skill exact。不使用MAX(revision)、不回退到旧常量、无隐式升级。
3. Logic发布按选中Skill声明的exact LogicRef核对；允许其他历史发布共存，不能把无关历史版本误判当前配置歧义。同一exact发布仍多义则拒绝。任务观察保留Skill/Binding/Logic exact引用，后续执行继续原有重验，不把观察变成执行许可。
4. 就绪刷新复用同一选择规则，仅处理职责参与者的active Binding。每个技能先唯一选择再触发刷新，缺失/歧义不额外刷新能力。
5. 测试覆盖重新发布并明确改绑、新版本存在但未改绑不自动升级、双active拒绝、缺失/错hash/跨租户拒绝、Logic历史共存、职责外绑定不刷新；保留现有就绪/审批测试。
6. 本波代码不写真实业务数据或技能配置；完成后先克隆验证技能发布与绑定，再实际配置、职责和安装激活。首链和八场景仍未完成。

具体文件：services/aos-api/aos_api/ecommerce_business_investigation_aip_authority.py、ecommerce_business_investigation_aip_composition.py、ecommerce_business_investigation_aip_readiness.py；对应services/aos-api/tests/test_ecommerce_business_investigation_aip_authority.py、test_ecommerce_business_investigation_aip_composition.py、test_ecommerce_business_investigation_aip_readiness.py。无迁移、不修改已有不可变技能记录。
