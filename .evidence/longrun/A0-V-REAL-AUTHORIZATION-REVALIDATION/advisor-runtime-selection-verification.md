# 经营参谋显式改绑恢复验证

2026-09-11，北京时间12:51，基线4d57ef29；任务A0V-ADVISOR-RUNTIME-DEPENDENCIES-20260911。

根因：经营调查生产组合与刷新器把D01r2/D02r2/D03r4的历史hash当作当前配置；合法新技能与新Logic发布后既不能改绑接续，又会把历史Logic发布误判为歧义。先补测试复现4项失败：重发改绑仍阻断、双active反而通过、缺技能先产生部分刷新、职责外绑定干扰改绑。

实现复用现有租户SkillBinding Owner：唯一active绑定选择具体不可变SkillRevision及hash，核验发布租户和所声明Logic exact；其他历史Logic发布可共存，同exact多发布仍拒绝。未绑定新版本不自动升级，两个版本同时active则拒绝，旧常量仅保留历史/测试引用。刷新前先完整选择，在能力刷新后再次核对技能选择和原Binding ID；职责外绑定不参与。未新增表/迁移、未直接改技能数据。

验证30通过：组合、刷新、职责权威及Profile catalog。覆盖新发布+明确改绑、未改绑不自动最新、双active、缺失/错hash/跨租户、历史Logic共存、职责外绑定以及刷新中第二版本激活拒绝。git diff --check通过。现有警告和退出JDBC日志错误仍在，pytest退出0。

实际aos_meta_head执行新查询兼容，正租户ready=false，技能/Logic引用0，阻断为技能未发布、职责计划缺失、无Run生产上下文；canary同样不可用并缺StageTemplate。本波未写实际业务数据、未做模型调用。真实库尚无已发布技能/Binding，因此成功改绑只由专项测试证明，不声称实际用户流完成。读快照不消除执行前并发变更，原执行门禁继续负责当前重验；刷新每次最多读取200条Binding的既有上限仍保留。

当前总依赖：Model/Route已各1，健康过期；37个evaluated技能、published0、能力/技能Binding0、6实例provisioning、职责计划0、已有approved安装无runtime绑定。旧审计显示2个passed Gate实际是Model/Route，不能计成技能完成2/37。数据来源仍未恢复，业务计划未生成。

下一波：隔离完整克隆先补首链D01/D02/D03及六职责所需的只读技能/文本能力绑定，沿Owner正式发布和评审；模型健康在需要时刷新，不把视频/语音接文本Route。再职责冻结、schema011候选兼容、激活既有approved安装、恢复真实数据、首次分析入口与自然事件接线。内容真实续跑、八场景、连续观察及发布决定仍未完成。m1串行、不push、230 L0挂起；API仍1100b936，后续准确重载。
