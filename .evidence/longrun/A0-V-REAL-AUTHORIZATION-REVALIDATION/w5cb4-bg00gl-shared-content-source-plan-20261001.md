# BG00GL 共用当前内容来源准备段

基线AOS-001052/m1 f8e04a02；执行GK纵向方案第一项，目标仍是合法首生Action→预算held。复习231-5/GK及当前ActionService：generic decide仅核Principal.roles，当前auth默认开发路径存在，不能直接将正式首生生产者开放在未核真实身份的通用路径。

## 本波文件与步骤

- services/aos-api/aos_api/ecommerce_content_budget_command_owner.py：将原_build_command中不依赖业务Action的核验抽为_prepare_sources，同一事务、同一原函数、原来源读取与锁，不复制状态机；返回dispatch/snapshot/task_ref/authorities/price/quota/cost_context/source_artifact_refs/fact_source_refs。返回值不含approval，不创建claim/hold/Provider，不执行GJ会更新fence的额度门；它只是已核来源准备，不能当授权或跨事务缓存。
- 原_build_command调用该函数，再原_approved_action、_approved_bound、command envelope、Host revalidate。原claim/execute/unknown流程不变；原预检的GrowthPlan/Method读取前移到来源段，失败仍禁止claim，不新增业务副作用。
- tests/extension_runtime/test_ecommerce_content_budget_command_owner.py：现有数字/风险参数组合测试先直接调用_prepare_sources，证明无需_approved_action、无approval authority/无claim，随后原_build_command仍调用审批并产原refs/金额。既有负向origin、claim、unknown及GJ真PG回归保留。组合替身只证明接线，不冒正式来源正向。
- 本plan/verification、446/D-waves、Task/Delivery/CAS/Prime。

RED缺_prepare_sources→提取实现→专项/相邻真实PG→复审。API/schema/UI不变，无browser；当前真实库只读、无迁移/重启。m1精确提交、不push。

## 后续必须闭合

BG00GM在此共用来源上实现首次Action预览/绑定/独立checker。先冻结身份入口：通用API不能凭开发Principal或客户端roles获得正式权威；显式首生合同默认拒绝、仅固定正式身份组合入口可写，同事务核当前member/metadata/markings/source/预算。不得用预算owner权限挪作业务审批，不新增影子审批体系。复用现有OIDC校验与ActionStore，原RETURN和未绑定草稿仍不获得执行权。最终须合法PG来源至held，而不是仅模板/替身测试。
