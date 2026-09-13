# CF2-6 当前技能集合读取验证

基线228d19d3。AnalysisSkillSetReader在当前职责/阶段Owner内按明确binding IDs读取AipSkillRegistry；绑定实例必须属于配置职责。复用AipSkillBindingReadinessService.evaluate只读重验发布、路由、能力与预算依赖，要求available、无原因、依赖hash不漂移。技能exact版本/hash/租户及Logic原发布记录再次核对；前后重读并输出派生集合。职责快照新增SourceOwner给出的安装代次/epoch。

Red缺模块8 failed；Green读取8+集合13+职责11+阶段12+桥接11=55 passed，/tmp/cf2-skill-reader-green.log。读取器测试使用显式Registry/Readiness/角色Owner/连接替身；不是主租户完整执行证据。AR2 1891/171/93全部错误为空，memory validate GREEN/AOS-000573，diff --check通过。

下一波CF2-7安装编译选择合同：复核受版本控制资源如何选择新兼容阶段与D01/D02/D03当前绑定，明确L1意图覆盖映射不得使用planned_not_published兼容表。随后CF3 Task/Brief/Context与Saga，CF4真实Host START，CF5新候选安装，CF6真实经营。未刷新主库TTL、未部署/push，230 L0挂起。
