# CF2-5 派生技能绑定集合验证

基线ab291bd9。新增AnalysisSkillBindingSet，以完整绑定、租户、安装代次/epoch、exact职责方案生成内容寻址SkillBindingSetRevision（revision1），无独立权限表。validate_current重解析嵌套可变值，精确比较当前绑定集合和安装，拒绝非active/available、过期、无评估、未来评估、依赖快照缺失、阻断原因。

Red缺模块8 failed；Green基础8 passed；增加就绪异常后集合13+职责11+阶段12+桥接11=47 passed（/tmp/cf2-skill-set-cumulative.log）。合同测试不证明真实SkillBinding当前读或Logic执行。AR2扫描1890/分类171/迁移93全部错误为空；memory validate GREEN/AOS-000573；diff --check通过。

下一波CF2-6：当前角色范围内真实绑定和Skill/Logic发布读取，回调前后重验，用该合同提供编译器精确集合resolver。仍需映射/模板选择和CF3–CF6。未主库写入或部署，不push，230 L0挂起。
