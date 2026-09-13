# CF2-2 职责合同层级修正验证

基线9e44ab0d。L1分析意图与职责运行能力不是同一命名空间，取消错误集合比较；改为领域responsibilityTemplateCode、compiler_profile、配置职责templateRef exact一致与现有模板权威解析，保留唯一配置、hash、frozen/ready/complete及Owner前后重读。

Red：正式build_responsibility_plan_request的六槽合同被旧读取器拒绝，1 failed/8 passed。Green：职责11、绑定11、既有composition9，共31 passed（/tmp/cf2-role-contract-green.log）。Owner/configuration/Store仍为明确替身；不是当前安装或真实技能执行证据。AR2 1889/171/93，所有错误为空；git diff --check通过；memoryctl validate GREEN，AOS-000573。

分析意图仍需后续Logic/Skill编译覆盖；不能以本波职责成功宣称CF2或业务链完成。已发现旧composition全租户选择模板且要求任务context，不能直接当成当前安装编译权威。下一波CF2-3精确阶段模板及其L1来源读取；随后技能、CF3事务准备、CF4真实START、CF5版本安装、CF6真实业务观察。未迁移主库、未部署、未push，230 L0挂起。
