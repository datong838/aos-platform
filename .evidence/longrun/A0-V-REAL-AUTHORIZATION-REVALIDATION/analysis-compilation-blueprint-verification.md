# CF2-8 安装包编译蓝图验证

基线1fa7424b，子Lease A0V-ANALYSIS-COMPILATION-BLUEPRINT-20260914。新增包analysis_compilation_blueprint.py，在既有analysis_advance增加纯kind。固定L1 exact引用、readonly compilerProfile、三阶段完整定义与D01/D02/D03技能标识；无租户binding/version/READY，不宣称L1意图全部验收，不授予执行权。

Red入口未实现8 failed；Green蓝图8+原START9=17 passed。正式CreateStageTemplateRequest合同内容一致（profile改为兼容readonly），校验body hash、重复确定性、输入不变、错误引用/额外字段/布尔revision拒绝。AR2 1892/171/93所有错误为空；requiredPaths登记新蓝图。未改旧候选、未部署、未调用模型或主库写。

下一波CF2-9 installed蓝图port与精确Host选择，随后CF3任务/简报/context及Saga，CF4真实START，CF5新候选安装，CF6真实经营验收。
