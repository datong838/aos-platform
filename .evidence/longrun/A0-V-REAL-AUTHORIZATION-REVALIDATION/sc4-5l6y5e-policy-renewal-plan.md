# Y5e 当前模型证据与策略续期候选

2026-09-16，m1 1cbaad2f，承接Y5d预算策略过期。沿用用户开发自测不限成本授权与原固定公共文本探针，不要求新费用授权，不扩大网络/数据权限。

1/6 读原a0v_exact_text_live_eval、text_eval_evidence/profiles及formal_text_model_renewal。使用新私有目录 snapshot-policy-renewal/text-evidence，text-readiness-v2固定三案例、每例单次原probe，无真实客户输入；失败/未知保留原intent，不隐式重试。原网络/Provider版本和审批范围由probe重验。

2/6 原freeze_plan(renew=True)只产生新budget/runtimePolicy/model/route候选，当前主库不publish。模型新鲜证据24h仍硬限制，不能把无限费用授权误当无限有效期。每层新ref依赖按原hash和CAS生成。

3/6 读回J原配置与原代次资源，核configure的fence/排空/commit/verify/enable全过程及dispatch cutover要求。原Host不stop，不释放已安装资源；原业务Run为PREPARING时不能伪造已drained。需要正式恢复/终止则登记Z先行依赖。

4/6 方案列出更新影响：budget、price、runtimePolicy、registeredModel、route、LogicGraph/skill/capability、ResponsibilityPlan、安装Configuration、binding epoch、dispatch current authority和十二源审批。不是修改一个effectiveUntil。核清原版本链及原Run保全路径后才下一波发布。

5/6 新固定探针实际结果、正式候选hash、只读主库前后版本与源Run/Claim不变；不把模型探针成功视为经营链成功。

6/6 证据/上下文/Receipt提交，后继波次以实际依赖排序实施正式更新，然后回Y5d、Y6d、Z/自然链与八工作台验收。新增开发文件仅在方案补齐具体路径后创建。

## 3/6–5/6 已核实的更新影响

新probe三例实际成功；原verified reader复核，候选planHash=f838a9c87bde03e74861d8e3e080c3862404f02dd4a9449c20cd2022df82e3a5，budget6/runtimePolicy6/model5/route5，有效至2026-09-17T11:18:04.157170Z。主库仍budget5；未发布任何候选。证据y5e-renewal-candidate-verification.json。

J配置e2fdde1f-ebdb-4863-b158-7204735f3fe8@1精确引用runtimePolicy5。原configuration stage支持后继配置，configure先fence再以GenerationDrainReader查所有旧epoch执行attempt，commit设置disabled/unknown，原PreparedJob的OwnedControlConsumer可在同代次enable；不是Host.stop，无需释放/复活资源。当前J runtime attempt0、三资源held，binding6/epoch3保持。但此事实不能代替待执行事务内排空，也不表示旧业务Run已终态。

发现必须先补的产品缺口：现有dispatch cutover prepare只接legacy组；activation为resumed后不能用原finalize覆盖新epoch；successor注册a0v056要求distinct retired predecessor。直接同代次configure/enable后，原十条dispatch仍绑定epoch3，不会自然承接新epoch。不能调用消费过的旧cutover脚本、SQL改epoch、创建新安装掩盖每次配置续期的问题。

下一波Y5f补“同安装同代次配置更新后的分发接续”技术方案并逐段实现：新请求须固定原resume/current refresh Receipt、新configuration/enable完成事实、新当前binding和完整operation集合、明确审批；原receipt不可改，新增refresh回执链。准入必须要求原配置更替已排空及无未知调用，原业务Run不自动改写；刷新后的current authority要被原路由与disable/detach reader共同识别。先做严格合同与拒绝测试，再PG原子Owner/权限/回执及路由生命周期集成，克隆演练后才允许主库更新。新功能归AR2已装电商配置维护，不实施230L0运行时装载扩展。

Y5d审批/定义、Y6d源组、Z旧任务、真实经营链和八工作台未完成。配置接续是“真实可配置、可恢复”目标缺口，不将三项模型探针当产品闭环。
