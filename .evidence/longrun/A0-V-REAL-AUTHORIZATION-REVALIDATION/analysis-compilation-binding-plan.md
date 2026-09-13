# CF1 精确编译绑定合同

基线6f80f789。新增services/aos-api/aos_api/ecommerce_analysis_compilation_binding.py及tests/test_ecommerce_analysis_compilation_binding.py。

合同记录tenant/install/generation/epoch、完整L1 domainProfile、L2 CompileBusinessInvestigationRequest和canonical contentHash。L1/L2 analysisType及阶段顺序一致且身份不可冒充；校验当前Case ACTIVE/hash/profile与Run exact血缘，复用CompileSaga输入校验。每次使用重解析和重算hash，拒绝嵌套对象变更。

只做绑定校验，不授予运行权、不创建角色/计划/回执。CF2才接当前安装配置；CF4真实START已知失败仍保留。定向测试规范构造及tenant/install/epoch/Case/Run/嵌套篡改拒绝。
